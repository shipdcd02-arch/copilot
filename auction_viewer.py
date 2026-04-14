# -*- coding: utf-8 -*-
"""
법원경매 뷰어 — Python Desktop App
court_auction.db를 읽어 브라우저로 시각화

구조: map_naver.py와 동일 (HTTP 서버 + Chrome 앱 모드)
향후 map_naver.py와 연계할 수 있도록 설계됨
"""

import sys, os, json, sqlite3, socket, threading, time, subprocess
import http.server, socketserver, urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "court_auction.db")

# ── 네이버 Maps (map_naver.py와 공유) ─────────────────────────────
CLIENT_ID = "ddzk96e01d"

# ── API 핸들러 ────────────────────────────────────────────────────
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def api_items(params):
    """물건 목록 (사이드바용)"""
    conn = _db()
    rows = conn.execute("""
        SELECT id, case_display, dept_name, addr_sido, addr_sigu, addr_dong,
               addr_ri, lot_number, building_name, category_name,
               appraisal_amt, min_sale_price, failed_bid_cnt, inquiry_cnt,
               auction_date, auction_time, area_list, land_type, note,
               wgs84_x, wgs84_y, first_seen, last_updated, last_sync
        FROM auction_items
        ORDER BY auction_date ASC, case_display ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def api_item_detail(params):
    """물건 상세 + lots + documents + changes"""
    item_id = params.get("id", [""])[0]
    conn = _db()

    item = conn.execute("SELECT * FROM auction_items WHERE id=?", (item_id,)).fetchone()
    if not item:
        conn.close()
        return {"error": "not found"}

    lots = conn.execute(
        "SELECT lot_no, address, area, land_type FROM item_lots WHERE item_id=? ORDER BY lot_no",
        (item_id,)
    ).fetchall()

    docs = conn.execute(
        "SELECT doc_type, doc_data, fetched_at FROM documents WHERE item_id=?",
        (item_id,)
    ).fetchall()

    changes = conn.execute(
        "SELECT field_name, old_value, new_value, changed_at FROM changes "
        "WHERE item_id=? ORDER BY changed_at DESC LIMIT 50",
        (item_id,)
    ).fetchall()

    land_info = conn.execute(
        "SELECT pnu, own_gbn, share_cnt, land_use_raw FROM land_info WHERE item_id=?",
        (item_id,)
    ).fetchone()

    building = conn.execute(
        "SELECT use_nm, build_year, total_area, ground_flrs, basement_flrs, struct_nm "
        "FROM building_info WHERE item_id=?",
        (item_id,)
    ).fetchone()

    trades = conn.execute(
        "SELECT trade_type, trade_date, trade_amt, area, floor, lot_no "
        "FROM trade_history WHERE item_id=? ORDER BY trade_date DESC LIMIT 10",
        (item_id,)
    ).fetchall()

    conn.close()

    result = dict(item)
    # raw_data는 이미 JSON 문자열
    if result.get("raw_data"):
        try:
            result["raw_data"] = json.loads(result["raw_data"])
        except Exception:
            pass

    result["lots"] = [dict(r) for r in lots]
    result["documents"] = {}
    for d in docs:
        doc_info = dict(d)
        try:
            doc_info["doc_data"] = json.loads(doc_info["doc_data"])
        except Exception:
            pass
        result["documents"][doc_info["doc_type"]] = doc_info

    result["changes"] = [dict(r) for r in changes]

    if land_info:
        li = dict(land_info)
        if li.get("land_use_raw"):
            try:
                li["land_use"] = json.loads(li["land_use_raw"])
            except Exception:
                li["land_use"] = None
        del li["land_use_raw"]
        result["land_info"] = li
    else:
        result["land_info"] = None

    result["building"] = dict(building) if building else None
    result["trades"]   = [dict(r) for r in trades]
    return result

def api_stats(params):
    """동기화 통계"""
    import importlib.util, sys as _sys
    conn = _db()
    total = conn.execute("SELECT COUNT(*) FROM auction_items").fetchone()[0]
    changed = conn.execute(
        "SELECT COUNT(DISTINCT item_id) FROM changes").fetchone()[0]
    last_sync = conn.execute(
        "SELECT finished_at FROM sync_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    # land_info 수집 건수
    land_cnt = 0
    try:
        land_cnt = conn.execute("SELECT COUNT(*) FROM land_info").fetchone()[0]
    except Exception:
        pass
    conn.close()
    # DATA_GO_KR_KEY 설정 여부 확인
    dg_key_set = False
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "court_auction", os.path.join(SCRIPT_DIR, "court_auction.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        dg_key_set = bool(getattr(mod, "DATA_GO_KR_KEY", ""))
    except Exception:
        pass
    return {
        "total_items": total,
        "changed_items": changed,
        "last_sync": last_sync[0] if last_sync else None,
        "land_info_cnt": land_cnt,
        "dg_key_set": dg_key_set,
    }

def api_sync_log(params):
    conn = _db()
    rows = conn.execute(
        "SELECT * FROM sync_log ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


DOC_TYPE_NAMES = {"detail": "물건상세", "survey": "현황조사서", "appraisal": "감정평가서"}

# 문서 타입 → 이미지 코드 매핑
# 000241=현황조사서, 000245=감정평가서, 나머지(000243/244/246)=물건상세 관련
APPRAISAL_CODE = "000245"
SURVEY_CODE    = "000241"   # dlt_ordTsPicDvs에서도 확인됨

def api_doc_view(params, item_id, doc_type):
    """문서 이미지 뷰어 페이지 — base64 JPEG 이미지를 페이지별로 표시"""
    conn = _db()
    item = conn.execute(
        "SELECT case_display, addr_sido, addr_sigu, addr_dong, addr_ri, lot_number "
        "FROM auction_items WHERE id=?", (item_id,)
    ).fetchone()

    # detail 문서에서 csPicLst(이미지) 가져오기
    detail_row = conn.execute(
        "SELECT doc_data, fetched_at FROM documents WHERE item_id=? AND doc_type='detail'",
        (item_id,)
    ).fetchone()

    # survey 문서에서 이미지 코드 확인
    survey_row = conn.execute(
        "SELECT doc_data FROM documents WHERE item_id=? AND doc_type='survey'",
        (item_id,)
    ).fetchone()

    conn.close()

    def esc(s):
        return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;") if s is not None else ""

    case_display = item["case_display"] if item else ""
    addr_parts = [item[k] for k in ("addr_sido","addr_sigu","addr_dong","addr_ri","lot_number") if item and item[k]]
    addr = " ".join(addr_parts)
    type_name = DOC_TYPE_NAMES.get(doc_type, doc_type)
    fetched = (detail_row["fetched_at"] or "").replace("T"," ")[:19] if detail_row else ""

    # ── 이미지 필터링 ──────────────────────────────────────────
    all_pics = []
    if detail_row:
        try:
            detail_doc = json.loads(detail_row["doc_data"])
            all_pics = detail_doc.get("dma_result", {}).get("csPicLst", [])
        except Exception:
            all_pics = []

    # survey 코드는 dlt_ordTsPicDvs에서 동적으로 읽음
    survey_code = SURVEY_CODE
    if survey_row:
        try:
            sdoc = json.loads(survey_row["doc_data"])
            dvs = sdoc.get("dlt_ordTsPicDvs", [])
            if dvs:
                survey_code = dvs[0].get("cortAuctnPicDvsCd", SURVEY_CODE)
        except Exception:
            pass

    if doc_type == "survey":
        pics = [p for p in all_pics if p.get("cortAuctnPicDvsCd") == survey_code]
    elif doc_type == "appraisal":
        pics = [p for p in all_pics if p.get("cortAuctnPicDvsCd") == APPRAISAL_CODE]
    else:  # detail: survey/appraisal 코드 제외 나머지 (또는 전체)
        exclude = {survey_code, APPRAISAL_CODE}
        pics = [p for p in all_pics if p.get("cortAuctnPicDvsCd") not in exclude]
        if not pics:  # 별도 이미지 없으면 전체 표시
            pics = all_pics

    # pageSeq 기준 정렬
    pics.sort(key=lambda p: int(p.get("pageSeq") or p.get("cortAuctnPicSeq") or 0))

    if not pics:
        return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"/>
<title>{esc(case_display)} {esc(type_name)}</title></head>
<body style="font-family:'Malgun Gothic',sans-serif;padding:40px;text-align:center;color:#888">
<p style="font-size:16px">이미지가 없습니다.</p>
<p style="font-size:12px;margin-top:8px">수집기를 다시 실행하거나 해당 문서가 없을 수 있습니다.</p>
</body></html>""", None

    # ── HTML 이미지 뷰어 생성 ──────────────────────────────────
    img_tags = []
    for i, p in enumerate(pics):
        b64 = p.get("picFile", "")
        if not b64:
            continue
        page_no = p.get("pageSeq") or (i + 1)
        img_tags.append(
            f'<div class="page">'
            f'<div class="pg-no">{page_no} / {len(pics)}</div>'
            f'<img src="data:image/jpeg;base64,{b64}" alt="페이지 {page_no}"/>'
            f'</div>'
        )

    pages_html = "\n".join(img_tags)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<title>{esc(case_display)} {esc(type_name)}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Malgun Gothic','Segoe UI',sans-serif;background:#404040;color:#fff}}
.hd{{background:#1565c0;color:#fff;padding:12px 20px;display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:10;box-shadow:0 2px 8px rgba(0,0,0,.4)}}
.hd h1{{font-size:15px;font-weight:700;flex:1}}
.hd .sub{{font-size:11px;opacity:.8}}
.hd .cnt{{font-size:12px;background:rgba(255,255,255,.2);padding:3px 10px;border-radius:12px}}
.pages{{display:flex;flex-direction:column;align-items:center;gap:12px;padding:20px 0}}
.page{{position:relative;background:#fff;box-shadow:0 4px 16px rgba(0,0,0,.5)}}
.pg-no{{position:absolute;top:8px;right:8px;background:rgba(0,0,0,.55);color:#fff;font-size:11px;padding:2px 8px;border-radius:10px}}
.page img{{display:block;max-width:min(900px,98vw);width:100%;height:auto}}
</style>
</head>
<body>
<div class="hd">
  <h1>&#128196; {esc(case_display)} — {esc(type_name)}</h1>
  <div class="sub">{esc(addr)}</div>
  <div class="cnt">{len(pics)}페이지</div>
</div>
<div class="pages">
{pages_html}
</div>
</body>
</html>"""
    return html, None


# ── HTML ──────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>법원경매 뷰어 - 통영지원</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--primary:#1565c0;--primary-light:#e3f2fd;--danger:#c62828;--success:#2e7d32;--warning:#f57f17;--bg:#f5f5f5;--card:#fff;--text:#222;--text2:#666;--border:#e0e0e0}
body{font-family:'Malgun Gothic','Segoe UI',sans-serif;height:100vh;display:flex;flex-direction:column;background:var(--bg)}

/* 헤더 */
header{height:50px;background:var(--primary);color:#fff;display:flex;align-items:center;padding:0 20px;gap:12px;flex-shrink:0}
header h1{font-size:15px;font-weight:700}
header .stats{margin-left:auto;font-size:11px;opacity:.85}
.hdr-btn{padding:4px 14px;border-radius:14px;border:1.5px solid rgba(255,255,255,.6);background:0;color:#fff;font-size:11px;font-weight:600;cursor:pointer}
.hdr-btn:hover{background:rgba(255,255,255,.2)}
.hdr-btn.active{background:#fff;color:var(--primary)}

/* 레이아웃 */
.main{display:flex;flex:1;overflow:hidden}

/* 사이드바 */
.sidebar{width:360px;background:var(--card);display:flex;flex-direction:column;border-right:1px solid var(--border);flex-shrink:0}
.sidebar-top{padding:10px 14px;border-bottom:1px solid var(--border);display:flex;gap:6px;align-items:center}
.sidebar-top input{flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:6px;font-size:12px;outline:none}
.sidebar-top input:focus{border-color:var(--primary)}
.sidebar-top .cnt{font-size:11px;color:var(--text2);white-space:nowrap}
.list{overflow-y:auto;flex:1}

.item{padding:10px 14px;border-bottom:1px solid #f0f0f0;cursor:pointer;transition:background .1s;position:relative}
.item:hover{background:#f8f9fa}
.item.active{background:var(--primary-light);border-left:3px solid var(--primary)}
.item .case-no{font-size:13px;font-weight:700;color:var(--text)}
.item .addr{font-size:11px;color:var(--text2);margin-top:2px;line-height:1.4}
.item .meta{display:flex;gap:8px;margin-top:4px;font-size:10px;flex-wrap:wrap}
.item .tag{padding:1px 6px;border-radius:8px;font-weight:600}
.tag-price{background:#fff3e0;color:#e65100}
.tag-fail{background:#fce4ec;color:var(--danger)}
.tag-cat{background:#e8eaf6;color:#283593}
.tag-new{background:#c8e6c9;color:var(--success)}
.tag-changed{background:#fff9c4;color:var(--warning)}

/* 상세 패널 */
.detail{flex:1;overflow-y:auto;padding:0}
.detail-empty{display:flex;align-items:center;justify-content:center;height:100%;color:#aaa;font-size:14px}

.detail-header{padding:16px 20px;background:var(--card);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10}
.detail-header .title{font-size:16px;font-weight:700;color:var(--text)}
.detail-header .sub{font-size:12px;color:var(--text2);margin-top:2px}

.detail-body{padding:16px 20px}

/* 정보 카드 */
.card{background:var(--card);border-radius:8px;padding:14px 16px;margin-bottom:12px;border:1px solid var(--border)}
.card-title{font-size:12px;font-weight:700;color:var(--primary);margin-bottom:8px;display:flex;align-items:center;gap:6px}
.card-title .icon{font-size:14px}
.info-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:6px 16px}
.info-row{display:flex;gap:6px}
.info-label{font-size:11px;color:var(--text2);min-width:70px;flex-shrink:0}
.info-value{font-size:12px;color:var(--text);font-weight:600;word-break:break-all}
.price-big{font-size:16px;color:var(--danger);font-weight:700}

/* 문서 버튼 */
.doc-btns{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.doc-btn{padding:8px 16px;border-radius:6px;border:1px solid var(--border);background:var(--card);font-size:12px;font-weight:600;cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:4px}
.doc-btn:hover{border-color:var(--primary);color:var(--primary);background:var(--primary-light)}
.doc-btn.active{background:var(--primary);color:#fff;border-color:var(--primary)}
.doc-btn .dot{width:6px;height:6px;border-radius:50%;background:#ccc}
.doc-btn.has-data .dot{background:var(--success)}

/* 문서 패널 */

/* 변경이력 */
.change-item{padding:6px 0;border-bottom:1px solid #f5f5f5;font-size:11px;display:flex;gap:8px;align-items:baseline}
.change-field{font-weight:700;color:var(--primary);min-width:80px}
.change-old{color:var(--danger);text-decoration:line-through}
.change-new{color:var(--success);font-weight:600}
.change-date{color:#aaa;font-size:10px;margin-left:auto;white-space:nowrap}

/* 목록 테이블 */
.lots-table{width:100%;border-collapse:collapse;font-size:11px}
.lots-table th{background:#f5f5f5;padding:6px 8px;text-align:left;font-weight:700;color:var(--text2);border-bottom:2px solid var(--border)}
.lots-table td{padding:6px 8px;border-bottom:1px solid #f0f0f0}

/* 탭 */
.tabs{display:flex;border-bottom:2px solid var(--border);margin-bottom:12px}
.tab{padding:8px 16px;font-size:12px;font-weight:600;color:var(--text2);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .15s}
.tab:hover{color:var(--text)}
.tab.active{color:var(--primary);border-bottom-color:var(--primary)}
.tab-content{display:none}
.tab-content.show{display:block}
</style>
</head>
<body>

<header>
  <svg width="18" height="18" viewBox="0 0 24 24" fill="#fff"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
  <h1>법원경매 뷰어 — 통영지원</h1>
  <button class="hdr-btn" onclick="toggleMap()">지도</button>
  <span class="stats" id="hdr-stats"></span>
</header>

<div class="main">
  <div class="sidebar">
    <div class="sidebar-top">
      <input type="text" id="search" placeholder="사건번호·주소·비고 검색..." oninput="filterList()"/>
      <span class="cnt" id="list-cnt"></span>
    </div>
    <div class="list" id="list"></div>
  </div>
  <div class="detail" id="detail">
    <div class="detail-empty">왼쪽 목록에서 물건을 선택하세요</div>
  </div>
</div>

<script>
var ALL_ITEMS=[], FILTERED=[], SELECTED=null, DETAIL_CACHE={};
var DATA_GO_KR_KEY_SET=false; /* court_auction.py에서 DATA_GO_KR_KEY 설정 여부 */

/* ── 초기 로드 ──────────────────────────── */
fetch('/api/items').then(r=>r.json()).then(data=>{
  ALL_ITEMS=data;
  fetch('/api/stats').then(r=>r.json()).then(s=>{
    DATA_GO_KR_KEY_SET=s.dg_key_set||false;
    var landTxt=s.land_info_cnt>0?(' | 토지정보 '+s.land_info_cnt+'건'):'';
    document.getElementById('hdr-stats').textContent=
      '물건 '+s.total_items+'건 | 변경 '+s.changed_items+'건'+landTxt+' | 최종동기화: '+(s.last_sync?s.last_sync.replace('T',' ').slice(0,19):'없음');
  });
  filterList();
});

/* ── 필터 ─────────────────────────────── */
function filterList(){
  var q=document.getElementById('search').value.toLowerCase();
  FILTERED=ALL_ITEMS.filter(function(it){
    if(!q) return true;
    return (it.case_display||'').toLowerCase().indexOf(q)>=0
      ||(it.addr_dong||'').indexOf(q)>=0
      ||(it.addr_ri||'').indexOf(q)>=0
      ||(it.building_name||'').indexOf(q)>=0
      ||(it.note||'').toLowerCase().indexOf(q)>=0
      ||(it.category_name||'').indexOf(q)>=0;
  });
  renderList();
}

function fmtKRW(n){
  if(!n||n<=0) return '-';
  var eok=Math.floor(n/1e8), man=Math.floor((n%1e8)/1e4);
  if(eok>0&&man>0) return eok+'억 '+man.toLocaleString()+'만';
  if(eok>0) return eok+'억';
  return man.toLocaleString()+'만';
}

function renderList(){
  var el=document.getElementById('list');
  document.getElementById('list-cnt').textContent=FILTERED.length+'건';
  el.innerHTML=FILTERED.map(function(it,i){
    var addr=(it.addr_sigu||'')+' '+(it.addr_dong||'')+' '+(it.addr_ri||'')+' '+(it.lot_number||'');
    var isNew=it.first_seen===it.last_updated;
    var isChanged=it.last_updated!==it.first_seen&&it.last_updated!==it.last_sync;
    return '<div class="item'+(SELECTED===it.id?' active':'')+'" data-id="'+it.id+'">'
      +'<div class="case-no">'+it.case_display+(it.building_name?' · '+it.building_name:'')+'</div>'
      +'<div class="addr">'+addr.trim()+'</div>'
      +'<div class="meta">'
      +'<span class="tag tag-price">'+fmtKRW(it.min_sale_price)+'</span>'
      +(it.failed_bid_cnt>0?'<span class="tag tag-fail">유찰 '+it.failed_bid_cnt+'회</span>':'')
      +(it.category_name?'<span class="tag tag-cat">'+it.category_name+'</span>':'')
      +(isNew?'<span class="tag tag-new">NEW</span>':'')
      +(isChanged?'<span class="tag tag-changed">변경</span>':'')
      +'</div></div>';
  }).join('');
}
document.getElementById('list').addEventListener('click',function(e){
  var item=e.target.closest('.item');
  if(item&&item.dataset.id) selectItem(item.dataset.id);
});
document.getElementById('detail').addEventListener('click',function(e){
  var btn=e.target.closest('.doc-btn[data-doc]');
  if(btn){
    var docType=btn.dataset.doc;
    var itemId=btn.dataset.id;
    if(!btn.classList.contains('has-data')){
      alert('수집된 문서가 없습니다. court_auction.py를 다시 실행하세요.');
      return;
    }
    window.open('/api/doc_view?id='+encodeURIComponent(itemId)+'&type='+encodeURIComponent(docType),'_blank');
  }
});

/* ── 물건 선택 ─────────────────────────── */
function selectItem(id){
  SELECTED=id;
  renderList();
  if(DETAIL_CACHE[id]){ renderDetail(DETAIL_CACHE[id]); return; }
  document.getElementById('detail').innerHTML='<div class="detail-empty">로딩 중...</div>';
  fetch('/api/detail?id='+encodeURIComponent(id)).then(r=>r.json()).then(function(d){
    DETAIL_CACHE[id]=d;
    renderDetail(d);
  });
}

/* ── 금액 포맷 ─────────────────────────── */
var FIELD_NAMES={
  status_code:'진행상태',item_status:'물건상태',appraisal_amt:'감정평가액',
  min_sale_price:'최저매각가',failed_bid_cnt:'유찰횟수',prev_sale_amt:'전회매각가',
  inquiry_cnt:'조회수',auction_date:'매각기일',settlement_date:'매각결정기일',
  auction_time:'매각시간',auction_place:'매각장소',note:'비고',special_cond:'특수조건'
};

function renderDetail(d){
  var addr=(d.addr_sido||'')+' '+(d.addr_sigu||'')+' '+(d.addr_dong||'')+' '+(d.addr_ri||'')+' '+(d.lot_number||'');
  var hasSurvey=d.documents&&d.documents.survey;
  var hasAppraisal=d.documents&&d.documents.appraisal;
  var hasDetail=d.documents&&d.documents.detail;

  var h='<div class="detail-header">'
    +'<div class="title">'+d.case_display+(d.building_name?' · '+d.building_name:'')+'</div>'
    +'<div class="sub">'+addr.trim()+' | '+(d.dept_name||'')+' | '+(d.court_name||'')+' '+(d.court_tel||'')+'</div>'
    +'</div>';

  h+='<div class="detail-body">';

  /* 가격 카드 */
  h+='<div class="card"><div class="card-title"><span class="icon">&#128176;</span> 가격 정보</div>'
    +'<div class="info-grid">'
    +'<div class="info-row"><span class="info-label">감정평가액</span><span class="info-value price-big">'+fmtKRW(d.appraisal_amt)+'원</span></div>'
    +'<div class="info-row"><span class="info-label">최저매각가</span><span class="info-value price-big" style="color:var(--primary)">'+fmtKRW(d.min_sale_price)+'원</span></div>'
    +'<div class="info-row"><span class="info-label">매각가율</span><span class="info-value">'+(d.appraisal_amt?Math.round(d.min_sale_price/d.appraisal_amt*100)+'%':'-')+'</span></div>'
    +'<div class="info-row"><span class="info-label">유찰횟수</span><span class="info-value" style="color:var(--danger)">'+(d.failed_bid_cnt||0)+'회</span></div>'
    +'<div class="info-row"><span class="info-label">조회수</span><span class="info-value">'+(d.inquiry_cnt||0)+'</span></div>'
    +'<div class="info-row"><span class="info-label">전회매각가</span><span class="info-value">'+fmtKRW(d.prev_sale_amt)+'원</span></div>'
    +'</div></div>';

  /* 기일 카드 */
  var ad=d.auction_date||'';
  var adFmt=ad?ad.slice(0,4)+'.'+ad.slice(4,6)+'.'+ad.slice(6,8):'';
  var at=d.auction_time||'';
  var atFmt=at?(at.slice(0,2)+':'+at.slice(2,4)):'';
  h+='<div class="card"><div class="card-title"><span class="icon">&#128197;</span> 매각기일</div>'
    +'<div class="info-grid">'
    +'<div class="info-row"><span class="info-label">매각기일</span><span class="info-value">'+adFmt+' '+atFmt+'</span></div>'
    +'<div class="info-row"><span class="info-label">매각장소</span><span class="info-value">'+(d.auction_place||'-')+'</span></div>'
    +'<div class="info-row"><span class="info-label">결정기일</span><span class="info-value">'+(d.settlement_date||'-')+'</span></div>'
    +'</div></div>';

  /* 물건 목록 (lots) */
  if(d.lots&&d.lots.length>0){
    h+='<div class="card"><div class="card-title"><span class="icon">&#128204;</span> 목록 ('+d.lots.length+'건)</div>'
      +'<table class="lots-table"><thead><tr><th>번호</th><th>소재지</th><th>면적</th><th>지목</th></tr></thead><tbody>';
    d.lots.forEach(function(l){
      h+='<tr><td>'+l.lot_no+'</td><td>'+l.address+'</td><td>'+l.area+'</td><td>'+l.land_type+'</td></tr>';
    });
    h+='</tbody></table></div>';
  }

  /* 비고 */
  if(d.note){
    h+='<div class="card"><div class="card-title"><span class="icon">&#128221;</span> 비고</div>'
      +'<pre style="font-size:12px;line-height:1.6;white-space:pre-wrap">'+escHtml(d.note)+'</pre></div>';
  }

  /* 토지 정보 카드 */
  if(d.land_info){
    var li=d.land_info;
    var ownStr=(li.own_gbn||'미수집');
    var shrStr=li.share_cnt>0?(li.share_cnt+'명'):'1명(단독)';
    h+='<div class="card"><div class="card-title"><span class="icon">&#127968;</span> 토지 정보</div>'
      +'<div class="info-grid">'
      +'<div class="info-row"><span class="info-label">소유구분</span><span class="info-value">'+escHtml(ownStr)+'</span></div>'
      +'<div class="info-row"><span class="info-label">공유인원</span><span class="info-value">'+escHtml(shrStr)+'</span></div>';
    if(li.pnu){
      h+='<div class="info-row"><span class="info-label">PNU</span><span class="info-value" style="font-size:10px;color:#888">'+escHtml(li.pnu)+'</span></div>';
    }
    h+='</div>';
    if(li.land_use&&li.land_use.length>0){
      h+='<div style="margin-top:8px"><div style="font-size:11px;font-weight:700;color:#555;margin-bottom:4px">토지이용계획</div>'
        +'<div style="display:flex;flex-wrap:wrap;gap:4px">';
      li.land_use.forEach(function(u){
        var label=(u.용도||u.구분||'').replace(/용도지역/g,'').trim();
        if(label) h+='<span style="background:#e3f2fd;color:#1565c0;font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600">'+escHtml(label)+'</span>';
      });
      h+='</div></div>';
    }else if(!DATA_GO_KR_KEY_SET){
      h+='<div style="font-size:11px;color:#aaa;margin-top:6px">토지이용계획: VWorld 조회 실패 또는 해당 필지 없음</div>';
    }
    h+='</div>';
  }

  /* 건축물 정보 카드 */
  if(d.building&&d.building.use_nm){
    var b=d.building;
    h+='<div class="card"><div class="card-title"><span class="icon">&#127963;</span> 건축물대장</div>'
      +'<div class="info-grid">'
      +'<div class="info-row"><span class="info-label">주용도</span><span class="info-value">'+escHtml(b.use_nm||'-')+'</span></div>'
      +'<div class="info-row"><span class="info-label">사용승인</span><span class="info-value">'+(b.build_year?b.build_year+'년':'-')+'</span></div>'
      +'<div class="info-row"><span class="info-label">연면적</span><span class="info-value">'+(b.total_area?b.total_area.toFixed(1)+'㎡':'-')+'</span></div>'
      +'<div class="info-row"><span class="info-label">층수</span><span class="info-value">'
        +(b.ground_flrs||b.basement_flrs?(('지상 '+(b.ground_flrs||0)+'층')+(b.basement_flrs?' / 지하 '+b.basement_flrs+'층':'')):'-')
        +'</span></div>'
      +'<div class="info-row"><span class="info-label">주구조</span><span class="info-value">'+escHtml(b.struct_nm||'-')+'</span></div>'
      +'</div></div>';
  }

  /* 실거래가 카드 */
  if(d.trades&&d.trades.length>0){
    h+='<div class="card"><div class="card-title"><span class="icon">&#128200;</span> 실거래가 (최근 '+d.trades.length+'건)</div>'
      +'<table class="lots-table"><thead><tr><th>거래일</th><th>금액</th><th>면적</th><th>층/지번</th></tr></thead><tbody>';
    d.trades.forEach(function(t){
      var dt=t.trade_date||'';
      var dtFmt=dt.length>=8?dt.slice(0,4)+'.'+dt.slice(4,6)+'.'+dt.slice(6,8):(dt||'-');
      var amtFmt=t.trade_amt?fmtKRW(t.trade_amt*10000)+'원':'-';
      var areaFmt=t.area?t.area.toFixed(1)+'㎡':'-';
      var floorLot=(t.floor?t.floor+'층':(t.lot_no||'-'));
      h+='<tr><td>'+dtFmt+'</td><td style="color:var(--danger);font-weight:700">'+amtFmt+'</td><td>'+areaFmt+'</td><td>'+escHtml(floorLot)+'</td></tr>';
    });
    h+='</tbody></table></div>';
  }

  /* 관련 문서 버튼 */
  h+='<div class="card"><div class="card-title"><span class="icon">&#128196;</span> 관련 문서</div>'
    +'<div class="doc-btns">'
    +'<button class="doc-btn'+(hasDetail?' has-data':'')+'" data-doc="detail" data-id="'+d.id+'"><span class="dot"></span> 물건상세</button>'
    +'<button class="doc-btn'+(hasSurvey?' has-data':'')+'" data-doc="survey" data-id="'+d.id+'"><span class="dot"></span> 현황조사서</button>'
    +'<button class="doc-btn'+(hasAppraisal?' has-data':'')+'" data-doc="appraisal" data-id="'+d.id+'"><span class="dot"></span> 감정평가서</button>'
    +'</div></div>';

  /* 변경이력 */
  if(d.changes&&d.changes.length>0){
    h+='<div class="card"><div class="card-title"><span class="icon">&#128260;</span> 변경이력 ('+d.changes.length+'건)</div>';
    d.changes.forEach(function(c){
      var fn=FIELD_NAMES[c.field_name]||c.field_name;
      h+='<div class="change-item">'
        +'<span class="change-field">'+fn+'</span>'
        +'<span class="change-old">'+escHtml(c.old_value||'(없음)')+'</span>'
        +'<span>&rarr;</span>'
        +'<span class="change-new">'+escHtml(c.new_value||'(없음)')+'</span>'
        +'<span class="change-date">'+c.changed_at.replace('T',' ').slice(0,19)+'</span>'
        +'</div>';
    });
    h+='</div>';
  }

  h+='</div>'; // detail-body
  document.getElementById('detail').innerHTML=h;

}

function escHtml(s){return s?s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'):''}

/* ── 지도 토글 (map_naver.py 연계 대비) ─── */
function toggleMap(){
  alert('지도 연동은 map_naver.py와 통합 시 활성화됩니다.');
}

</script>
</body>
</html>
"""


# ── HTTP 서버 ─────────────────────────────────────────────────────
def start_server(port):
    html_bytes = HTML.encode("utf-8")

    API_MAP = {
        "/api/items":    api_items,
        "/api/detail":   api_item_detail,
        "/api/stats":    api_stats,
        "/api/sync_log": api_sync_log,
    }

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if parsed.path == "/api/doc_view":
                item_id = params.get("id", [""])[0]
                doc_type = params.get("type", ["detail"])[0]
                html_doc, err = api_doc_view(params, item_id, doc_type)
                if err:
                    body = f"<html><body><p style='color:red'>{err}</p></body></html>".encode("utf-8")
                else:
                    body = html_doc.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path in API_MAP:
                result = API_MAP[parsed.path](params)
                body = json.dumps(result, ensure_ascii=False, default=str).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html_bytes)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(html_bytes)

        def log_message(self, *a):
            pass

    class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
    server = ThreadedServer(("localhost", port), Handler)
    server.serve_forever()


def find_free_port(start=8090):
    for p in range(start, start + 20):
        try:
            with socket.socket() as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("localhost", p))
                return p
        except OSError:
            continue
    return None


def find_chrome():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"DB 파일이 없습니다: {DB_PATH}")
        print("먼저 court_auction.py를 실행하세요.")
        sys.exit(1)

    port = find_free_port()
    if not port:
        print("포트를 찾을 수 없습니다.")
        sys.exit(1)

    t = threading.Thread(target=start_server, args=(port,))
    t.start()
    time.sleep(0.3)

    chrome = find_chrome()
    url = f"http://localhost:{port}"

    if chrome:
        user_data = os.path.join(os.environ.get("TEMP", "."), "auction_viewer_profile")
        subprocess.Popen([
            chrome, f"--app={url}",
            f"--user-data-dir={user_data}",
            "--window-size=1400,850",
            "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        ])
        print(f"법원경매 뷰어 실행 중 (port {port})")
        try:
            t.join()
        except KeyboardInterrupt:
            pass
    else:
        import webbrowser
        webbrowser.open(url)
        print(f"브라우저에서 열었습니다: {url}")
        input("종료하려면 Enter...")
