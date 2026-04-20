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

    try:
        land_info = conn.execute(
            "SELECT pnu, own_gbn, share_cnt, land_use_raw FROM land_info WHERE item_id=?",
            (item_id,)
        ).fetchone()
    except Exception:
        land_info = None

    try:
        building = conn.execute(
            "SELECT use_nm, build_year, total_area, ground_flrs, basement_flrs, struct_nm "
            "FROM building_info WHERE item_id=?",
            (item_id,)
        ).fetchone()
    except Exception:
        building = None

    try:
        trades = conn.execute(
            "SELECT trade_type, trade_date, trade_amt, area, floor, lot_no "
            "FROM trade_history WHERE item_id=? ORDER BY trade_date DESC LIMIT 10",
            (item_id,)
        ).fetchall()
    except Exception:
        trades = []

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
    # DATA_GO_KR_KEY 설정 여부 확인 (court_auction.py에서 직접 읽기)
    dg_key_set = False
    try:
        ca_path = os.path.join(SCRIPT_DIR, "court_auction.py")
        with open(ca_path, encoding="utf-8") as _f:
            for _line in _f:
                if _line.strip().startswith("DATA_GO_KR_KEY"):
                    _val = _line.split("=", 1)[1].strip().strip('"').strip("'")
                    dg_key_set = bool(_val)
                    break
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

# detail의 csPicLst 내 cortAuctnPicDvsCd 코드
APPRAISAL_CODE = "000245"
SURVEY_CODE    = "000241"


def _fmt_ymd(s):
    """YYYYMMDD → YYYY.MM.DD"""
    s = str(s or "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}.{s[4:6]}.{s[6:]}"
    return s


def _strip_tags(s):
    """HTML 태그 제거, <br> → 줄바꿈"""
    import re
    s = re.sub(r"<br\s*/?>", "\n", str(s or ""), flags=re.I)
    return re.sub(r"<[^>]+>", "", s).strip()


def _render_survey_form(doc, esc):
    """현황조사서를 양식 형태 HTML로 렌더링"""
    info  = doc.get("dma_curstExmnMngInf", {})
    rlets = doc.get("dlt_ordTsRlet", [])
    lsers = doc.get("dlt_ordTsLserLtn", [])
    mrgs  = doc.get("dlt_curstExmnDpcnMrg", [])

    court = esc(info.get("cortOfcNm") or "")
    h = '<div class="form-doc">'
    if court:
        h += f'<div class="court-name">{court}</div>'
    h += '<div class="form-title">현 황 조 사 서</div>'

    # ① 기본 정보 테이블
    h += '<table class="info-tbl">'
    cs_no = esc(info.get("userCsNo") or "")
    if cs_no:
        h += f'<tr><th>사건번호</th><td colspan="3">{cs_no}</td></tr>'
    rcpt = _fmt_ymd(info.get("exmndcRcptnYmd"))
    send = _fmt_ymd(info.get("exmndcSndngYmd"))
    if rcpt or send:
        h += f'<tr><th>접수일</th><td>{esc(rcpt)}</td><th>발송일</th><td>{esc(send)}</td></tr>'
    exmn = str(info.get("exmnDtDts") or "").strip()
    if exmn:
        h += f'<tr><th>조사일시</th><td colspan="3">{esc(exmn)}</td></tr>'
    h += '</table>'

    # ② 부동산의 표시
    if rlets:
        h += '<div class="sec-hd">■ 부동산의 표시</div>'
        h += '<table class="data-tbl"><thead><tr><th>번호</th><th>소재지</th><th>지목</th><th>면적</th><th>점유 현황</th></tr></thead><tbody>'
        for i, r in enumerate(rlets, 1):
            addr = esc(r.get("printSt") or
                       " ".join(filter(None, [r.get("adongSdNm"), r.get("adongSggNm"),
                                              r.get("adongEmdNm"), r.get("adongRiNm"),
                                              r.get("rprsLtnoAddr")])))
            ldcg = esc(r.get("ldcgDts") or "")
            area = esc(r.get("objctArDts") or "")
            poss = esc(_strip_tags(r.get("gdsPossCtt") or ""))
            h += f'<tr><td class="tc">{i}</td><td>{addr}</td><td class="tc">{ldcg}</td><td class="tc">{area}</td><td>{poss}</td></tr>'
        h += '</tbody></table>'

    # ③ 임대차 관계
    h += '<div class="sec-hd">■ 임대차 관계</div>'
    if lsers:
        h += '<table class="data-tbl"><thead><tr><th>임차인</th><th>점유부분</th><th>보증금</th><th>차임</th><th>임대차기간</th></tr></thead><tbody>'
        for r in lsers:
            h += (f'<tr><td>{esc(r.get("lesrNm",""))}</td>'
                  f'<td>{esc(_strip_tags(r.get("ocupPart","")))}</td>'
                  f'<td>{esc(r.get("dpstAmt",""))}</td>'
                  f'<td>{esc(r.get("mntlyRnt",""))}</td>'
                  f'<td>{esc(r.get("lesPrDts",""))}</td></tr>')
        h += '</tbody></table>'
    else:
        h += '<p class="none-txt">해당 없음</p>'

    # ④ 현황조사 내용 (있을 때만)
    valid_mrgs = [m for m in mrgs if m.get("userCsNo") == info.get("userCsNo") or not m.get("userRletCsNo")]
    ctt_list = [_strip_tags(m.get("dpcnMrgCtt") or m.get("ctt") or "") for m in mrgs]
    ctt_list = [c for c in ctt_list if c]
    if ctt_list:
        h += '<div class="sec-hd">■ 현황조사 내용</div>'
        for ctt in ctt_list:
            h += f'<div class="text-block">{esc(ctt)}</div>'

    h += '</div>'
    return h


def _fmt_krw(v):
    """숫자 → 억/만원 표기"""
    try:
        n = int(v)
    except (TypeError, ValueError):
        return str(v or "-")
    if n <= 0:
        return "-"
    eok = n // 100_000_000
    man = (n % 100_000_000) // 10_000
    if eok and man:
        return f"{eok}억 {man:,}만원"
    if eok:
        return f"{eok}억원"
    return f"{man:,}만원"


def _render_appraisal_form(appr_doc, detail_doc, esc):
    """감정평가서를 양식 형태 HTML로 렌더링 (detail 문서 데이터 포함)"""
    info  = appr_doc.get("dma_ordTsIndvdAeeWevlInf", {})
    mrgs  = appr_doc.get("dlt_dpcnMrgCsLst", [])

    # detail 문서에서 추가 정보
    d_result  = detail_doc.get("dma_result", {})
    gds_info  = d_result.get("dspslGdsDxdyInfo", {})
    objct_lst = d_result.get("gdsDspslObjctLst", [])
    dxdy_lst  = d_result.get("gdsDspslDxdyLst", [])

    court = esc(info.get("cortOfcNm") or "")
    h = '<div class="form-doc">'
    if court:
        h += f'<div class="court-name">{court}</div>'
    h += '<div class="form-title">감 정 평 가 서</div>'

    # ① 기본 정보
    h += '<table class="info-tbl">'
    cs_no = esc(info.get("userCsNo") or gds_info.get("userCsNo") or "")
    if cs_no:
        h += f'<tr><th>사건번호</th><td colspan="3">{cs_no}</td></tr>'
    no    = esc(info.get("aeeWevlNo") or "")
    if court or no:
        h += f'<tr><th>법원</th><td>{court}</td><th>감정서번호</th><td>{no}</td></tr>'
    examr = esc(info.get("aeeEvlExamrNm") or "")
    exmn  = _fmt_ymd(info.get("exmnYmd"))
    if examr or exmn:
        h += f'<tr><th>감정평가사</th><td>{examr}</td><th>감정일</th><td>{esc(exmn)}</td></tr>'
    wrt  = _fmt_ymd(info.get("wrtYmd"))
    crtr = _fmt_ymd(info.get("dspslPrcCrtrYmd"))
    if wrt or crtr:
        h += f'<tr><th>작성일</th><td>{esc(wrt)}</td><th>기준일</th><td>{esc(crtr)}</td></tr>'
    # 총 감정가
    total_amt = gds_info.get("aeeEvlAmt") or info.get("aeeEvlAmt")
    if total_amt:
        h += f'<tr><th>총 감정가액</th><td colspan="3" style="color:#c62828;font-size:15px;font-weight:700">{_fmt_krw(total_amt)}</td></tr>'
    h += '</table>'

    # ② 물건별 감정가액 (detail의 gdsDspslObjctLst)
    if objct_lst:
        h += '<div class="sec-hd">■ 물건별 감정가액</div>'
        h += '<table class="data-tbl"><thead><tr><th>번호</th><th>소재지</th><th>지목</th><th>면적</th><th>감정가액</th></tr></thead><tbody>'
        for i, obj in enumerate(objct_lst, 1):
            addr = esc(obj.get("userPrintSt") or obj.get("rprsLtnoAddr") or "")
            ldcg = esc(obj.get("ldcgDts") or "")
            area = esc(obj.get("objctArDts") or "")
            amt  = _fmt_krw(obj.get("aeeEvlAmt"))
            h += f'<tr><td class="tc">{i}</td><td>{addr}</td><td class="tc">{ldcg}</td><td class="tc">{area}</td><td class="tc" style="color:#c62828;font-weight:700">{amt}</td></tr>'
        h += '</tbody></table>'

    # ③ 권리관계 / 특기사항 (detail의 dspslGdsDxdyInfo)
    rights_rows = []
    for label, key in [
        ("인수되는 권리", "ndstrcRghCtt"),
        ("지상권 존재",   "sprfcExstcDts"),
        ("담보권 설정",   "tprtyRnkHypthcStngDts"),
    ]:
        val = str(gds_info.get(key) or "").strip()
        if val:
            rights_rows.append((label, val))

    if rights_rows:
        h += '<div class="sec-hd">■ 권리관계</div>'
        h += '<table class="info-tbl">'
        for label, val in rights_rows:
            h += f'<tr><th>{esc(label)}</th><td colspan="3">{esc(val)}</td></tr>'
        h += '</table>'

    # ④ 특기사항 (gdsSpcfcRmk)
    rmk = _strip_tags(str(gds_info.get("gdsSpcfcRmk") or gds_info.get("dspslGdsRmk") or "").strip())
    if rmk:
        h += '<div class="sec-hd">■ 특기사항</div>'
        h += f'<div class="text-block">{esc(rmk)}</div>'

    # ⑤ 감정의견 (appraisal doc)
    opinion = str(info.get("fstmEvlDcsnOponCtt") or "").strip().strip('"')
    if opinion and opinion != "감정서 참조":
        h += '<div class="sec-hd">■ 감정의견</div>'
        h += f'<div class="text-block">{esc(opinion)}</div>'

    # ⑥ 매각기일 이력 (gdsDspslDxdyLst)
    RESULT_CD = {"001": "낙찰", "002": "유찰", "003": "취하", "004": "취소", "005": "연기"}
    if dxdy_lst:
        h += '<div class="sec-hd">■ 매각기일 이력</div>'
        h += '<table class="data-tbl"><thead><tr><th>기일</th><th>최저매각가</th><th>결과</th></tr></thead><tbody>'
        for d2 in sorted(dxdy_lst, key=lambda x: x.get("dxdyYmd", ""), reverse=True):
            ymd  = _fmt_ymd(d2.get("dxdyYmd"))
            prc  = _fmt_krw(d2.get("tsLwsDspslPrc") or d2.get("dspslAmt"))
            rcd  = d2.get("auctnDxdyRsltCd", "")
            res  = RESULT_CD.get(rcd, rcd)
            color = ("#2e7d32" if rcd == "001" else "#c62828" if rcd == "002" else "#555")
            h += f'<tr><td class="tc">{esc(ymd)}</td><td class="tc">{prc}</td><td class="tc" style="color:{color};font-weight:700">{esc(res)}</td></tr>'
        h += '</tbody></table>'

    # ⑦ 감정평가 내용 텍스트 (있을 때만)
    ctt_list = [_strip_tags(m.get("dpcnMrgCtt") or m.get("ctt") or "") for m in mrgs]
    ctt_list = [c for c in ctt_list if c]
    if ctt_list:
        h += '<div class="sec-hd">■ 감정평가 내용</div>'
        for ctt in ctt_list:
            h += f'<div class="text-block">{esc(ctt)}</div>'

    h += '</div>'
    return h


_FORM_CSS = """
.form-doc{background:#fff;color:#111;max-width:794px;margin:24px auto 0;
  padding:36px 48px 40px;box-shadow:0 6px 32px rgba(0,0,0,.55);
  font-size:12.5px;line-height:1.7;font-family:'Malgun Gothic','Segoe UI',sans-serif}
.form-title{font-size:22px;font-weight:900;text-align:center;letter-spacing:.2em;
  padding:0 0 16px;margin-bottom:20px;border-bottom:3px double #111}
.court-name{font-size:13px;font-weight:700;text-align:center;margin-bottom:4px;color:#333}
.info-tbl{width:100%;border-collapse:collapse;margin-bottom:20px}
.info-tbl th{background:#f0f0f0;border:1px solid #888;padding:5px 10px;
  font-size:12px;color:#333;min-width:80px;text-align:center;white-space:nowrap;font-weight:700}
.info-tbl td{border:1px solid #888;padding:5px 10px;color:#111;font-weight:600}
.sec-hd{font-size:13px;font-weight:800;color:#111;margin:22px 0 6px;
  padding:4px 10px;background:#e8e8e8;border-left:4px solid #333;letter-spacing:.05em}
.data-tbl{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px}
.data-tbl th{background:#d8d8d8;border:1px solid #888;padding:5px 8px;
  font-weight:800;color:#111;text-align:center}
.data-tbl td{border:1px solid #aaa;padding:5px 8px;vertical-align:top;color:#111}
.tc{text-align:center}
.tr{text-align:right}
.none-txt{font-size:12px;color:#666;margin:4px 0 12px;padding:6px 10px;
  background:#fafafa;border:1px dashed #ccc}
.text-block{background:#fafafa;border:1px solid #ccc;
  padding:10px 14px;font-size:12px;white-space:pre-wrap;margin-bottom:10px;line-height:1.8}
.pic-label{color:#999;font-size:11px;font-weight:700;text-align:center;
  padding:24px 0 8px;letter-spacing:.08em;border-top:1px dashed #ccc;margin-top:12px}
.tag-red{color:#c62828;font-weight:700}
.tag-blue{color:#1565c0;font-weight:700}
.tag-green{color:#2e7d32;font-weight:700}
"""


def api_doc_view(params, item_id, doc_type):
    """문서 뷰어 — 양식 형태 + 이미지"""
    conn = _db()
    item = conn.execute(
        "SELECT case_display, addr_sido, addr_sigu, addr_dong, addr_ri, lot_number "
        "FROM auction_items WHERE id=?", (item_id,)
    ).fetchone()

    target_row = conn.execute(
        "SELECT doc_data, fetched_at FROM documents WHERE item_id=? AND doc_type=?",
        (item_id, doc_type)
    ).fetchone()

    detail_row = conn.execute(
        "SELECT doc_data, fetched_at FROM documents WHERE item_id=? AND doc_type='detail'",
        (item_id,)
    ).fetchone()

    conn.close()

    def esc(s):
        return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;") if s is not None else ""

    case_display = item["case_display"] if item else ""
    addr_parts = [item[k] for k in ("addr_sido","addr_sigu","addr_dong","addr_ri","lot_number") if item and item[k]]
    addr = " ".join(addr_parts)
    type_name = DOC_TYPE_NAMES.get(doc_type, doc_type)

    # ── 문서 파싱 ───────────────────────────────────────────────
    target_doc = {}
    fetched = ""
    if target_row:
        fetched = (target_row["fetched_at"] or "").replace("T", " ")[:19]
        try:
            target_doc = json.loads(target_row["doc_data"])
        except Exception:
            pass

    detail_doc = {}
    if detail_row:
        if not fetched:
            fetched = (detail_row["fetched_at"] or "").replace("T", " ")[:19]
        try:
            detail_doc = json.loads(detail_row["doc_data"])
        except Exception:
            pass

    # ── 이미지 수집 (detail의 csPicLst에서 코드로 분류) ────────
    all_pics = detail_doc.get("dma_result", {}).get("csPicLst", [])

    dvs = target_doc.get("dlt_ordTsPicDvs", [])
    survey_codes = {d.get("cortAuctnPicDvsCd") for d in dvs if d.get("cortAuctnPicDvsCd")} or {SURVEY_CODE}

    if doc_type == "survey":
        pics = [p for p in all_pics if p.get("cortAuctnPicDvsCd") in survey_codes]
    elif doc_type == "appraisal":
        pics = [p for p in all_pics if p.get("cortAuctnPicDvsCd") == APPRAISAL_CODE]
    else:
        exclude = survey_codes | {APPRAISAL_CODE}
        pics = [p for p in all_pics if p.get("cortAuctnPicDvsCd") not in exclude]
        if not pics:
            pics = all_pics

    pics.sort(key=lambda p: int(p.get("pageSeq") or p.get("cortAuctnPicSeq") or 0))

    # ── 양식 HTML 렌더링 ────────────────────────────────────────
    form_html = ""
    if doc_type == "survey" and target_doc:
        form_html = _render_survey_form(target_doc, esc)
    elif doc_type == "appraisal" and target_doc:
        form_html = _render_appraisal_form(target_doc, detail_doc, esc)

    # ── 이미지 HTML ─────────────────────────────────────────────
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

    if not form_html and not img_tags:
        return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"/>
<title>{esc(case_display)} {esc(type_name)}</title></head>
<body style="font-family:'Malgun Gothic',sans-serif;padding:40px;text-align:center;color:#888">
<p style="font-size:16px">수집된 내용이 없습니다.</p>
<p style="font-size:12px;margin-top:8px">court_auction.py를 다시 실행하거나 해당 문서가 없을 수 있습니다.</p>
</body></html>""", None

    pic_count_txt = f"{len(img_tags)}페이지" if img_tags else "이미지 없음"
    pic_label = '<div class="pic-label">— 관련 사진 —</div>' if form_html and img_tags else ""

    pdf_filename = f"{case_display}_{type_name}.pdf".replace(" ", "_").replace("/", "-")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<title>{esc(case_display)} {esc(type_name)}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Malgun Gothic','Segoe UI',sans-serif;background:#555;color:#fff}}
.hd{{background:#1565c0;color:#fff;padding:10px 16px;display:flex;align-items:center;
  gap:10px;position:sticky;top:0;z-index:10;box-shadow:0 2px 8px rgba(0,0,0,.4)}}
.hd h1{{font-size:15px;font-weight:700;flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hd .sub{{font-size:11px;opacity:.8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  max-width:160px;flex-shrink:1}}
.hd .cnt{{font-size:12px;background:rgba(255,255,255,.2);padding:3px 10px;border-radius:12px;flex-shrink:0}}
.hd .fetch{{font-size:10px;opacity:.6;flex-shrink:0;white-space:nowrap}}
.hd .pdf-btn{{padding:6px 16px;border-radius:14px;border:1.5px solid rgba(255,255,255,.9);
  background:transparent;color:#fff;font-size:12px;font-weight:700;cursor:pointer;
  white-space:nowrap;flex-shrink:0;text-decoration:none;display:inline-block}}
.hd .pdf-btn:hover{{background:rgba(255,255,255,.25)}}
{_FORM_CSS}
.pages{{display:flex;flex-direction:column;align-items:center;gap:12px;padding:0 0 24px}}
.page{{position:relative;background:#fff;box-shadow:0 4px 16px rgba(0,0,0,.5)}}
.pg-no{{position:absolute;top:8px;right:8px;background:rgba(0,0,0,.55);
  color:#fff;font-size:11px;padding:2px 8px;border-radius:10px}}
.page img{{display:block;max-width:min(960px,98vw);width:100%;height:auto}}

@media print{{
  @page{{margin:15mm 12mm;size:A4}}
  body{{background:#fff;color:#222}}
  .hd{{display:none}}
  .form-doc{{box-shadow:none;border-radius:0;margin:0;padding:0;max-width:100%}}
  .pages{{gap:0;padding:0}}
  .page{{box-shadow:none;page-break-inside:avoid;margin-bottom:8px}}
  .pg-no{{display:none}}
  .page img{{max-width:100%;width:100%}}
  .data-tbl,table{{page-break-inside:avoid}}
  .sec-hd{{page-break-after:avoid}}
}}
</style>
</head>
<body>
<div class="hd">
  <h1>&#128196; {esc(case_display)} — {esc(type_name)}</h1>
  <div class="sub">{esc(addr)}</div>
  <div class="cnt">{pic_count_txt}</div>
  {f'<div class="fetch">수집: {esc(fetched)}</div>' if fetched else ''}
  <button class="pdf-btn" id="pdfBtn" onclick="savePdf()">&#128438; PDF 저장</button>
</div>
{form_html}
{pic_label}
<div class="pages">
{pages_html}
</div>
<script>
async function savePdf() {{
  const btn = document.getElementById('pdfBtn');
  btn.textContent = '⏳ 생성 중...';
  btn.disabled = true;
  try {{
    const res = await fetch('/api/doc_pdf?id={esc(item_id)}&type={esc(doc_type)}');
    const data = await res.json();
    if (data.ok) {{
      btn.textContent = '✅ 저장 완료';
      btn.title = data.path;
      setTimeout(() => {{ btn.textContent = '🖨 PDF 저장'; btn.disabled = false; }}, 3000);
    }} else {{
      alert('오류: ' + data.error);
      btn.textContent = '🖨 PDF 저장';
      btn.disabled = false;
    }}
  }} catch(e) {{
    alert('요청 실패: ' + e);
    btn.textContent = '🖨 PDF 저장';
    btn.disabled = false;
  }}
}}
</script>
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
            elif parsed.path == "/api/doc_pdf":
                item_id  = params.get("id",   [""])[0]
                doc_type = params.get("type", ["detail"])[0]
                pdf_bytes, err = generate_pdf_bytes(item_id, doc_type, port)
                if err or not pdf_bytes:
                    result = json.dumps({"ok": False, "error": err or "PDF 생성 실패"}, ensure_ascii=False)
                else:
                    conn = _db()
                    row = conn.execute(
                        "SELECT case_display FROM auction_items WHERE id=?", (item_id,)
                    ).fetchone()
                    conn.close()
                    case = (row["case_display"] if row else item_id).replace("/", "-")
                    type_name = DOC_TYPE_NAMES.get(doc_type, doc_type)
                    filename = f"{case}_{type_name}.pdf"
                    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
                    os.makedirs(downloads, exist_ok=True)
                    save_path = os.path.join(downloads, filename)
                    with open(save_path, "wb") as f:
                        f.write(pdf_bytes)
                    result = json.dumps({"ok": True, "path": save_path}, ensure_ascii=False)
                body = result.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
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


def generate_pdf_bytes(item_id, doc_type, port):
    """headless Chrome으로 HTML을 PDF로 변환 (file:// 방식, 네트워크 불필요)"""
    import tempfile
    chrome = find_chrome()
    if not chrome:
        return None, "Chrome/Edge를 찾을 수 없습니다"

    # HTML을 임시 파일로 저장
    html_doc, err = api_doc_view({}, item_id, doc_type)
    if err or not html_doc:
        return None, err or "HTML 생성 실패"

    tmp_dir = tempfile.mkdtemp()
    html_path = os.path.join(tmp_dir, "doc.html")
    pdf_path  = os.path.join(tmp_dir, "doc.pdf")

    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_doc)

        file_url = "file:///" + html_path.replace("\\", "/")

        subprocess.run([
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-extensions",
            f"--print-to-pdf={pdf_path}",
            "--print-to-pdf-no-header",
            file_url,
        ], capture_output=True, timeout=60)

        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            with open(pdf_path, "rb") as f:
                return f.read(), None
        return None, "PDF 생성 실패 (Chrome 오류)"
    except Exception as e:
        return None, str(e)
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


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
