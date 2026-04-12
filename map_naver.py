"""
네이버 지도 시각화 - Python Desktop App
Chrome 앱 모드로 실행 (별도 패키지 설치 불필요)
"""

import sys
import os
import json
import socket
import threading
import time
import subprocess
import http.server
import socketserver

# ── 네이버 Maps Client ID ───────────────────────────────────────────
CLIENT_ID = "ddzk96e01d"

# ── 샘플 주소 데이터 ────────────────────────────────────────────────
LOCATIONS = [
    {"name": "서울시청",          "address": "서울특별시 중구 세종대로 110",     "lat": 37.5663, "lng": 126.9779, "color": "#e53935"},
    {"name": "경복궁",            "address": "서울특별시 종로구 사직로 161",     "lat": 37.5796, "lng": 126.9770, "color": "#8e24aa"},
    {"name": "강남역",            "address": "서울특별시 강남구 강남대로 396",   "lat": 37.4979, "lng": 127.0276, "color": "#1e88e5"},
    {"name": "상암 월드컵경기장", "address": "서울특별시 마포구 월드컵북로 396", "lat": 37.5683, "lng": 126.8971, "color": "#43a047"},
    {"name": "롯데월드타워",      "address": "서울특별시 송파구 올림픽로 300",   "lat": 37.5126, "lng": 127.1021, "color": "#fb8c00"},
    {"name": "인천국제공항",      "address": "인천광역시 중구 공항로 272",       "lat": 37.4602, "lng": 126.4407, "color": "#00897b"},
]
# ────────────────────────────────────────────────────────────────────

LOCATIONS_JSON = json.dumps(LOCATIONS, ensure_ascii=False)

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

    markers.push(marker);
    iws.push(iw);

    var el = document.createElement('div');
    el.className = 'item';
    el.innerHTML = '<div class="item-bar" style="background:' + loc.color + '"></div>'
      + '<div class="item-info">'
      + '<div class="item-name">' + (i+1) + '. ' + loc.name + '</div>'
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

  // ── 지적도 토글 ──────────────────────────────────────────────
  var cadastralLayer = null;
  window.toggleCadastral = function() {{
    var btn = document.getElementById('cadastral-btn');
    if (!cadastralLayer) cadastralLayer = new naver.maps.CadastralLayer();
    if (btn.classList.contains('active')) {{
      cadastralLayer.setMap(null);
      btn.classList.remove('active');
    }} else {{
      cadastralLayer.setMap(map);
      btn.classList.add('active');
    }}
  }};

  // ── 위성지도 토글 ─────────────────────────────────────────────
  window.toggleSatellite = function() {{
    var btn = document.getElementById('satellite-btn');
    if (btn.classList.contains('active')) {{
      map.setMapTypeId(naver.maps.MapTypeId.NORMAL);
      btn.classList.remove('active');
    }} else {{
      map.setMapTypeId(naver.maps.MapTypeId.HYBRID);
      btn.classList.add('active');
    }}
  }};

  // ── 지도 클릭 → 주소 역지오코딩 ─────────────────────────────
  var addrIW = new naver.maps.InfoWindow({{
    borderColor: '#333',
    borderWidth: 1,
    anchorSize: new naver.maps.Size(10, 10),
    anchorSkew: true,
    anchorColor: '#333'
  }});

  naver.maps.Event.addListener(map, 'click', function(e) {{
    var coord = e.coord;
    addrIW.setContent('<div style="padding:10px 14px;font-size:13px;color:#555">&#9203; 주소 조회 중...</div>');
    iws.forEach(function(w) {{ w.close(); }});
    addrIW.open(map, coord);

    naver.maps.Service.reverseGeocode({{
      coords: coord,
      orders: [naver.maps.Service.OrderType.ADDR, naver.maps.Service.OrderType.ROAD_ADDR].join(',')
    }}, function(status, response) {{
      if (status !== naver.maps.Service.Status.OK) {{
        addrIW.setContent('<div style="padding:10px 14px;font-size:13px;color:#e53935">주소를 가져올 수 없습니다.</div>');
        return;
      }}
      var addr = response.v2 && response.v2.address;
      var roadAddr = addr ? (addr.roadAddress || '') : '';
      var jibunAddr = addr ? (addr.jibunAddress || '') : '';
      var lat = coord.lat().toFixed(5);
      var lng = coord.lng().toFixed(5);

      var html = '<div style="padding:12px 16px;min-width:220px;font-family:Malgun Gothic,sans-serif;line-height:1.6">';
      html += '<div style="font-size:11px;font-weight:700;color:#03c75a;letter-spacing:0.5px;margin-bottom:6px">&#128205; 클릭 위치</div>';
      if (roadAddr) html += '<div style="font-size:13px;color:#222;margin-bottom:2px">' + roadAddr + '</div>';
      if (jibunAddr) html += '<div style="font-size:12px;color:#666">' + jibunAddr + '</div>';
      if (!roadAddr && !jibunAddr) html += '<div style="font-size:13px;color:#888">주소 정보 없음</div>';
      html += '<div style="font-size:11px;color:#bbb;margin-top:7px;padding-top:6px;border-top:1px solid #eee">' + lat + '&deg;N, ' + lng + '&deg;E</div>';
      html += '</div>';
      addrIW.setContent(html);
    }});
  }});
}};
</script>
</body>
</html>
"""

# ── HTTP 서버 ─────────────────────────────────────────────────────────
def start_server(port):
    data = HTML.encode("utf-8")
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(data)
        def log_message(self, *a): pass
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

# ── Chrome 실행 경로 탐색 ─────────────────────────────────────────────
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
            "--window-size=1150,700",
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
        print("종료하려면 Enter를 누르세요...")
        input()
