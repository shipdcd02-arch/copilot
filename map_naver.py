"""
네이버 지도 시각화 - Python Desktop App
Chrome 앱 모드로 실행 (별도 패키지 설치 불필요)
"""

import sys
import os
import re
import json
import socket
import threading
import time
import subprocess
import http.server
import socketserver
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ── 네이버 Maps Client ID ───────────────────────────────────────────
CLIENT_ID = "ddzk96e01d"

# ── VWorld 개별공시지가 API 키 ───────────────────────────────────────
# 발급: https://www.vworld.kr → 마이포탈 → 나의 오픈API → 인증키관리
VWORLD_API_KEY = "598605FC-B443-3667-8F2B-ECD35D089286"

# ── 샘플 주소 데이터 ────────────────────────────────────────────────
LOCATIONS = [
    {"name": "서울시청",          "address": "서울특별시 중구 세종대로 110",     "lat": 37.5663, "lng": 126.9779, "color": "#e53935"},
    {"name": "경복궁",            "address": "서울특별시 종로구 사직로 161",     "lat": 37.5796, "lng": 126.9770, "color": "#8e24aa"},
    {"name": "강남역",            "address": "서울특별시 강남구 강남대로 396",   "lat": 37.4979, "lng": 127.0276, "color": "#1e88e5"},
    {"name": "상암 월드컵경기장", "address": "서울특별시 마포구 월드컵북로 396", "lat": 37.5683, "lng": 126.8971, "color": "#43a047"},
    {"name": "롯데월드타워",      "address": "서울특별시 송파구 올림픽로 300",   "lat": 37.5126, "lng": 127.1021, "color": "#fb8c00"},
    {"name": "인천국제공항",      "address": "인천광역시 중구 공항로 272",       "lat": 37.4602, "lng": 126.4407, "color": "#00897b"},
]

LOCATIONS_JSON = json.dumps(LOCATIONS, ensure_ascii=False)


# ── VWorld: 좌표 → PNU 변환 ────────────────────────────────────────
def _get_pnu(lat, lng):
    """좌표(WGS84) → 필지번호(PNU 19자리) 변환"""
    try:
        url = ("https://api.vworld.kr/req/address"
               + "?service=address&request=getAddress&version=2.0"
               + "&crs=epsg:4326"
               + "&point=" + str(lng) + "," + str(lat)
               + "&type=parcel&format=json"
               + "&key=" + VWORLD_API_KEY
               + "&domain=localhost")
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        result = (data.get("response") or {}).get("result") or []
        if not result:
            return None
        struct = result[0].get("structure") or {}
        code  = struct.get("level4LC", "")   # 법정동코드 10자리 (지번주소용)
        jibun = str(struct.get("level5") or "0")
        # "212-8번", "31번지" 등 한글/특수문자 제거 → 숫자와 '-' 만 남김
        jibun = re.sub(r"[^0-9\-]", "", jibun)
        if not code or len(code) != 10:
            return None
        parts = jibun.split("-")
        bon   = parts[0] if parts and parts[0] else "0"
        bu    = parts[1] if len(parts) > 1 and parts[1] else "0"
        # PNU = 법정동코드(10) + 대지구분(1: 토지=1, 임야=2) + 본번(4) + 부번(4)
        # 토지(1) 먼저 시도, 결과 없으면 임야(2) 재시도는 get_land_info에서 처리
        return [code + "1" + bon.zfill(4) + bu.zfill(4),
                code + "2" + bon.zfill(4) + bu.zfill(4)]
    except Exception:
        return None


# ── VWorld: PNU + 연도 → 공시지가 조회 ───────────────────────────────
def _fetch_price(args):
    pnu, year, api_key = args
    try:
        url = ("https://api.vworld.kr/ned/data/getIndvdLandPriceAttr"
               + "?key=" + api_key
               + "&pnu=" + pnu
               + "&stdrYear=" + str(year)
               + "&domain=localhost"
               + "&format=json&numOfRows=1&pageNo=1")
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # 응답 최상위 키: indvdLandPrices → field 배열
        body = data.get("indvdLandPrices") or {}
        rows = body.get("field") or []
        if not rows:
            return year, None
        price = int(float(str(rows[0].get("pblntfPclnd") or 0))) or None
        return year, price
    except Exception:
        return year, None


# ── VWorld: PNU → 토지 면적(m²) 조회 ────────────────────────────────
def _get_area(pnu, api_key):
    try:
        url = ("https://api.vworld.kr/ned/data/ladfrlList"
               + "?key=" + api_key
               + "&pnu=" + pnu
               + "&domain=localhost"
               + "&format=json&numOfRows=1&pageNo=1")
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # 응답 최상위 키: ladfrlVOList → ladfrlVOList (중첩)
        outer = data.get("ladfrlVOList") or {}
        rows  = outer.get("ladfrlVOList") or []
        if not rows:
            return None
        return float(str(rows[0].get("lndpclAr") or 0)) or None
    except Exception:
        return None


def get_land_info(lat, lng):
    if not VWORLD_API_KEY:
        return {"error": "NO_API_KEY"}

    # 1. 좌표 → PNU 후보 목록 (토지=1, 임야=2)
    pnu_list = _get_pnu(lat, lng)
    if not pnu_list:
        return {"error": "NO_DATA"}

    cur   = datetime.now().year
    years = list(range(cur - 9, cur + 1))

    # 2. PNU 후보를 순서대로 시도 (토지 먼저, 안 되면 임야)
    pnu = None
    prices = {}
    for candidate in pnu_list:
        test_prices = {}
        with ThreadPoolExecutor(max_workers=5) as ex:
            for yr, price in ex.map(_fetch_price, [(candidate, y, VWORLD_API_KEY) for y in years]):
                if price:
                    test_prices[yr] = price
        if test_prices:
            pnu = candidate
            prices = test_prices
            break

    if not prices:
        return {"error": "NO_DATA"}

    # 3. 면적 조회
    area = _get_area(pnu, VWORLD_API_KEY)

    latest = max(prices.keys())
    pyeong = round(area / 3.3058, 1) if area else None
    total  = int(area * prices[latest]) if area else None

    return {
        "area_m2":     area,
        "area_pyeong": pyeong,
        "prices":      prices,
        "latest_year": latest,
        "total":       total,
    }


# ── HTML ────────────────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>네이버 지도 시각화</title>
  <script type="text/javascript"
    src="https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId={CLIENT_ID}&submodules=geocoder">
  </script>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:'Malgun Gothic','Segoe UI',sans-serif; height:100vh; display:flex; flex-direction:column; }}
    header {{
      height:52px; background:#03c75a; color:white;
      display:flex; align-items:center; padding:0 20px; gap:8px;
      box-shadow:0 2px 6px rgba(0,0,0,0.15); flex-shrink:0;
    }}
    header h1 {{ font-size:16px; font-weight:700; }}
    header .count {{ margin-left:auto; font-size:12px; opacity:0.85; }}
    .map-btn {{
      padding:5px 13px; border-radius:16px; border:1.5px solid rgba(255,255,255,0.7);
      background:transparent; color:white; font-size:12px; font-weight:600;
      cursor:pointer; transition:all 0.2s; white-space:nowrap;
    }}
    .map-btn:hover {{ background:rgba(255,255,255,0.2); }}
    .map-btn.active {{ background:white; color:#03c75a; border-color:white; }}
    .body {{ display:flex; flex:1; overflow:hidden; }}
    .sidebar {{
      width:280px; background:white; display:flex; flex-direction:column;
      box-shadow:2px 0 8px rgba(0,0,0,0.08); flex-shrink:0;
    }}
    .sidebar-title {{
      padding:14px 16px 8px; font-size:11px; font-weight:700;
      color:#888; text-transform:uppercase; letter-spacing:0.5px;
      border-bottom:1px solid #eee;
    }}
    .list {{ overflow-y:auto; flex:1; }}
    .item {{
      display:flex; align-items:stretch; border-bottom:1px solid #f0f0f0;
      cursor:pointer; transition:background 0.15s;
    }}
    .item:hover {{ background:#f5fff9; }}
    .item.active {{ background:#e6f9ef; border-left:3px solid #03c75a; }}
    .item-bar {{ width:4px; flex-shrink:0; }}
    .item-info {{ padding:12px 12px 12px 10px; flex:1; }}
    .item-name {{ font-size:13px; font-weight:700; color:#222; margin-bottom:4px; }}
    .item-addr {{ font-size:11px; color:#888; line-height:1.4; }}
    #map {{ flex:1; }}
  </style>
</head>
<body>
<header>
  <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
  </svg>
  <h1>네이버 지도 시각화</h1>
  <button class="map-btn" id="cadastral-btn" onclick="toggleCadastral()">지적도</button>
  <button class="map-btn" id="satellite-btn" onclick="toggleSatellite()">위성</button>
  <span class="count" id="count-label"></span>
</header>
<div class="body">
  <div class="sidebar">
    <div class="sidebar-title">위치 목록</div>
    <div class="list" id="list"></div>
  </div>
  <div id="map"></div>
</div>
<script>
window.onload = function() {{

  /* ── 클립보드 복사 ─────────────────────────────────────────── */
  window.doCopy = function(el) {{
    var text = el.getAttribute('data-copy');
    var flash = function() {{
      var prev = el.style.background;
      el.style.background = '#d4edda';
      setTimeout(function() {{ el.style.background = prev || ''; }}, 700);
    }};
    if (navigator.clipboard) {{
      navigator.clipboard.writeText(text).then(flash).catch(function() {{
        fallback(text); flash();
      }});
    }} else {{ fallback(text); flash(); }}
  }};

  function fallback(text) {{
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
  }}

  /* copyRow: 클릭하면 data-copy 값을 복사하는 행 */
  function copyRow(copyText, labelHtml) {{
    var safe = copyText.replace(/&/g,'&amp;').replace(/"/g,'&quot;');
    return '<div data-copy="' + safe + '" onclick="doCopy(this)"'
      + ' style="cursor:pointer;padding:3px 6px;margin:1px 0;border-radius:4px;'
      + 'display:flex;align-items:center;justify-content:space-between;transition:background 0.15s"'
      + ' title="클릭하여 복사">'
      + '<span style="flex:1">' + labelHtml + '</span>'
      + '<span style="font-size:10px;color:#ccc;margin-left:6px;flex-shrink:0">&#128203;</span>'
      + '</div>';
  }}

  /* 금액 한국식 표기 */
  function fmtKRW(n) {{
    if (!n || n <= 0) return '-';
    n = Math.round(n);
    var eok = Math.floor(n / 100000000);
    var man = Math.floor((n % 100000000) / 10000);
    if (eok > 0 && man > 0) return eok + '억 ' + man.toLocaleString() + '만원';
    if (eok > 0) return eok + '억원';
    return man.toLocaleString() + '만원';
  }}

  /* ── 팝업 HTML 빌더 ──────────────────────────────────────── */
  function buildPopup(roadAddr, jibunAddr, lat, lng, landData) {{
    var latS = parseFloat(lat).toFixed(5);
    var lngS = parseFloat(lng).toFixed(5);
    var coordStr = latS + 'N, ' + lngS + 'E';

    var h = '<div style="font-family:Malgun Gothic,sans-serif;min-width:270px;max-width:330px;'
          + 'padding:12px 14px;line-height:1.55;font-size:12px">';

    /* 주소 */
    h += '<div style="font-size:10px;font-weight:700;color:#03c75a;letter-spacing:.5px;margin-bottom:4px">&#128205; 클릭 위치</div>';
    if (roadAddr) h += copyRow(roadAddr,  '<span style="font-size:13px;color:#222">' + roadAddr + '</span>');
    if (jibunAddr) h += copyRow(jibunAddr, '<span style="font-size:12px;color:#666">' + jibunAddr + '</span>');
    if (!roadAddr && !jibunAddr) h += '<div style="color:#999;font-size:12px;padding:2px 6px">주소 정보 없음</div>';
    h += copyRow(coordStr, '<span style="font-size:11px;color:#aaa">' + coordStr + '</span>');

    h += '<div style="border-top:1px solid #eee;margin:8px 0 6px"></div>';

    /* 토지 정보 */
    if (landData === null) {{
      h += '<div style="color:#aaa;font-size:12px;padding:4px 6px">&#9203; 토지정보 조회 중...</div>';
    }} else if (landData.error === 'NO_API_KEY') {{
      h += '<div style="color:#bbb;font-size:11px;padding:3px 6px">'
        + '공시지가 조회 불가 — map_naver.py의<br>LAND_API_KEY를 설정하세요.'
        + '</div>';
    }} else if (landData.error) {{
      h += '<div style="color:#bbb;font-size:11px;padding:3px 6px">토지 정보 없음 (임야·도로·하천 등)</div>';
    }} else {{

      /* 면적 */
      if (landData.area_m2) {{
        var areaM2  = landData.area_m2.toLocaleString(undefined, {{maximumFractionDigits:1}}) + ' m\u00b2';
        var areaPy  = landData.area_pyeong.toLocaleString(undefined, {{maximumFractionDigits:1}}) + '\ud3c9';
        var areaStr = areaM2 + ' (' + areaPy + ')';
        h += '<div style="font-size:10px;font-weight:700;color:#1565c0;letter-spacing:.5px;margin-bottom:3px">&#128208; 토지 면적</div>';
        h += copyRow(areaStr,
          '<span style="font-size:13px;color:#1a237e;font-weight:600">' + areaM2 + '</span>'
          + '<span style="color:#888;margin-left:6px">' + areaPy + '</span>');
        h += '<div style="border-top:1px solid #eee;margin:7px 0 5px"></div>';
      }}

      /* 공시지가 10년 */
      var years = Object.keys(landData.prices).map(Number).sort();
      if (years.length > 0) {{
        h += '<div style="font-size:10px;font-weight:700;color:#6a1b9a;letter-spacing:.5px;margin-bottom:4px">&#128202; 개별공시지가 (원/m\u00b2)</div>';
        var maxP = 0;
        for (var yi = 0; yi < years.length; yi++) {{ if (landData.prices[years[yi]] > maxP) maxP = landData.prices[years[yi]]; }}

        for (var yi = 0; yi < years.length; yi++) {{
          var yr = years[yi];
          var pr = landData.prices[yr];
          var bw = Math.round(pr / maxP * 72);
          var isLatest = (yr === landData.latest_year);
          var barColor = isLatest ? '#2e7d32' : '#9575cd';
          var prStr = pr.toLocaleString() + '\uc6d0';
          var cpText = yr + '\ub144 \uacf5\uc2dc\uc9c0\uac00: ' + pr.toLocaleString() + '\uc6d0/m\u00b2';
          var barHtml =
            '<div style="display:flex;align-items:center;width:100%;gap:5px">'
            + '<span style="font-size:10px;color:#777;width:34px;flex-shrink:0">' + yr + '</span>'
            + '<div style="flex:1;height:7px;background:#ede7f6;border-radius:3px;overflow:hidden">'
            + '<div style="width:' + bw + '%;height:100%;background:' + barColor + ';border-radius:3px"></div></div>'
            + '<span style="font-size:10px;color:' + (isLatest ? '#2e7d32' : '#444') + ';'
            + 'font-weight:' + (isLatest ? '700' : '400') + ';white-space:nowrap;min-width:72px;text-align:right">'
            + prStr + '</span>'
            + '</div>';
          h += copyRow(cpText, barHtml);
        }}
        h += '<div style="border-top:1px solid #eee;margin:7px 0 5px"></div>';
      }}

      /* 전체 토지 가치 */
      if (landData.total && landData.area_m2) {{
        var latestPr  = landData.prices[landData.latest_year] || 0;
        var totalStr  = fmtKRW(landData.total);
        var formulaStr = latestPr.toLocaleString() + '\uc6d0/m\u00b2 \u00d7 '
                       + landData.area_m2.toLocaleString(undefined, {{maximumFractionDigits:1}}) + 'm\u00b2';
        h += '<div style="font-size:10px;font-weight:700;color:#b71c1c;letter-spacing:.5px;margin-bottom:3px">'
          + '&#128176; ' + landData.latest_year + '\ub144 \uacf5\uc2dc\uc9c0\uac00 \uae30\uc900 \ud1a0\uc9c0 \uac00\uce58</div>';
        h += copyRow(String(landData.total),
          '<span style="font-size:15px;font-weight:700;color:#c62828">' + totalStr + '</span>');
        h += copyRow(formulaStr,
          '<span style="font-size:10px;color:#999">' + formulaStr + '</span>');
      }}
    }}

    h += '</div>';
    return h;
  }}

  /* ── 지도 초기화 ───────────────────────────────────────────── */
  var LOCATIONS = {LOCATIONS_JSON};
  document.getElementById('count-label').textContent = '총 ' + LOCATIONS.length + '개 위치';

  var map = new naver.maps.Map('map', {{
    center: new naver.maps.LatLng(37.54, 127.0),
    zoom: 10
  }});

  var sel = null;
  var markers = [], iws = [], items = [];

  LOCATIONS.forEach(function(loc, i) {{
    var marker = new naver.maps.Marker({{
      position: new naver.maps.LatLng(loc.lat, loc.lng),
      map: map,
      icon: {{
        content: '<div style="position:relative;width:36px;height:48px;filter:drop-shadow(0 2px 4px rgba(0,0,0,.3))">'
          + '<svg width="36" height="48" viewBox="0 0 36 48" xmlns="http://www.w3.org/2000/svg">'
          + '<path d="M18 0C8.06 0 0 8.06 0 18c0 11.25 18 30 18 30S36 29.25 36 18C36 8.06 27.94 0 18 0z"'
          + ' fill="' + loc.color + '" stroke="white" stroke-width="1.5"/>'
          + '<circle cx="18" cy="18" r="8" fill="white"/>'
          + '<text x="18" y="22" text-anchor="middle" font-size="10" font-weight="bold"'
          + ' fill="' + loc.color + '" font-family="Malgun Gothic,sans-serif">' + (i+1) + '</text>'
          + '</svg></div>',
        anchor: new naver.maps.Point(18, 48)
      }}
    }});

    var iw = new naver.maps.InfoWindow({{
      content: '<div style="padding:12px 14px;min-width:180px;font-family:Malgun Gothic,sans-serif">'
        + '<b style="font-size:14px">' + (i+1) + '. ' + loc.name + '</b>'
        + '<div style="font-size:12px;color:#666;margin-top:4px">' + loc.address + '</div>'
        + '<span style="display:inline-block;margin-top:8px;padding:2px 10px;border-radius:20px;'
        + 'font-size:11px;color:#fff;background:' + loc.color + '">위치 확인</span></div>',
      borderColor: loc.color, borderWidth: 2,
      pixelOffset: new naver.maps.Point(0, -10)
    }});

    naver.maps.Event.addListener(marker, 'click', (function(idx, w) {{
      return function() {{
        select(idx);
        iws.forEach(function(x) {{ x.close(); }});
        addrIW.close();
        w.open(map, markers[idx]);
      }};
    }})(i, iw));

    markers.push(marker); iws.push(iw);

    var el = document.createElement('div');
    el.className = 'item';
    el.innerHTML = '<div class="item-bar" style="background:' + loc.color + '"></div>'
      + '<div class="item-info"><div class="item-name">' + (i+1) + '. ' + loc.name + '</div>'
      + '<div class="item-addr">' + loc.address + '</div></div>';
    el.onclick = (function(idx, w) {{
      return function() {{
        select(idx);
        map.panTo(new naver.maps.LatLng(LOCATIONS[idx].lat, LOCATIONS[idx].lng));
        map.setZoom(15);
        iws.forEach(function(x) {{ x.close(); }});
        addrIW.close();
        w.open(map, markers[idx]);
      }};
    }})(i, iw);
    document.getElementById('list').appendChild(el);
    items.push(el);
  }});

  var b = new naver.maps.LatLngBounds();
  LOCATIONS.forEach(function(l) {{ b.extend(new naver.maps.LatLng(l.lat, l.lng)); }});
  map.fitBounds(b, {{top:50, right:50, bottom:50, left:50}});

  function select(i) {{
    if (sel !== null) items[sel].classList.remove('active');
    items[i].classList.add('active');
    sel = i;
    items[i].scrollIntoView({{behavior:'smooth', block:'nearest'}});
  }}

  /* ── 지적도 / 위성 토글 ─────────────────────────────────── */
  var cadastralLayer = null;
  window.toggleCadastral = function() {{
    var btn = document.getElementById('cadastral-btn');
    if (!cadastralLayer) cadastralLayer = new naver.maps.CadastralLayer();
    if (btn.classList.contains('active')) {{ cadastralLayer.setMap(null); btn.classList.remove('active'); }}
    else {{ cadastralLayer.setMap(map); btn.classList.add('active'); }}
  }};

  window.toggleSatellite = function() {{
    var btn = document.getElementById('satellite-btn');
    if (btn.classList.contains('active')) {{ map.setMapTypeId(naver.maps.MapTypeId.NORMAL);  btn.classList.remove('active'); }}
    else {{ map.setMapTypeId(naver.maps.MapTypeId.HYBRID); btn.classList.add('active'); }}
  }};

  /* ── 지도 클릭 → 주소 + 공시지가 팝업 ─────────────────────── */
  var addrIW = new naver.maps.InfoWindow({{
    borderColor: '#555', borderWidth: 1,
    anchorSize: new naver.maps.Size(10, 10),
    anchorSkew: true, anchorColor: '#555'
  }});

  var clickSeq = 0;

  naver.maps.Event.addListener(map, 'click', function(e) {{
    var seq = ++clickSeq;
    var coord = e.coord;
    var lat = coord.lat(), lng = coord.lng();

    addrIW.setContent('<div style="padding:12px 16px;font-size:13px;color:#aaa;font-family:Malgun Gothic">&#9203; 조회 중...</div>');
    iws.forEach(function(w) {{ w.close(); }});
    addrIW.open(map, coord);

    /* 역지오코딩 */
    naver.maps.Service.reverseGeocode({{
      coords: coord,
      orders: [naver.maps.Service.OrderType.ADDR, naver.maps.Service.OrderType.ROAD_ADDR].join(',')
    }}, function(status, response) {{
      if (seq !== clickSeq) return;
      var roadAddr = '', jibunAddr = '';
      if (status === naver.maps.Service.Status.OK) {{
        var addr = response.v2 && response.v2.address;
        roadAddr  = addr ? (addr.roadAddress  || '') : '';
        jibunAddr = addr ? (addr.jibunAddress || '') : '';
      }}

      /* 주소 표시, 토지정보는 로딩 중 */
      addrIW.setContent(buildPopup(roadAddr, jibunAddr, lat, lng, null));

      /* 공시지가 조회 (Python 프록시) */
      fetch('/api/land?lat=' + lat + '&lng=' + lng)
        .then(function(r) {{ return r.json(); }})
        .then(function(d) {{ if (seq === clickSeq) addrIW.setContent(buildPopup(roadAddr, jibunAddr, lat, lng, d)); }})
        .catch(function() {{ if (seq === clickSeq) addrIW.setContent(buildPopup(roadAddr, jibunAddr, lat, lng, {{error:'FETCH_ERROR'}})); }});
    }});
  }});

}};
</script>
</body>
</html>
"""


# ── HTTP 서버 ─────────────────────────────────────────────────────────
def start_server(port):
    html_bytes = HTML.encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/land":
                params = urllib.parse.parse_qs(parsed.query)
                lat = params.get("lat", [""])[0]
                lng = params.get("lng", [""])[0]
                result = get_land_info(lat, lng)
                body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html_bytes)))
                self.end_headers()
                self.wfile.write(html_bytes)

        def log_message(self, *a):
            pass

    server = socketserver.TCPServer(("localhost", port), Handler)
    server.serve_forever()


def find_free_port(start=8080):
    for p in range(start, start + 20):
        try:
            with socket.socket() as s:
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
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    for name in ["chrome", "google-chrome", "chromium", "msedge"]:
        try:
            result = subprocess.run(["where", name], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().splitlines()[0]
        except Exception:
            pass
    return None


# ── 메인 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = find_free_port()
    if not port:
        print("포트를 찾을 수 없습니다.")
        sys.exit(1)

    t = threading.Thread(target=start_server, args=(port,), daemon=True)
    t.start()
    time.sleep(0.5)

    chrome = find_chrome()
    url = f"http://localhost:{port}"

    if chrome:
        user_data = os.path.join(os.environ.get("TEMP", "."), "map_app_profile")
        proc = subprocess.Popen([
            chrome,
            f"--app={url}",
            f"--user-data-dir={user_data}",
            "--window-size=1200,750",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
        ])
        print(f"✅ 지도 앱 실행 중 (port {port}) — 창을 닫으면 종료됩니다.")
        proc.wait()
    else:
        import webbrowser
        webbrowser.open(url)
        print(f"✅ 브라우저에서 열었습니다: {url}")
        input("종료하려면 Enter를 누르세요...")
