import os
import glob
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, colorchooser
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import datetime
import struct
import tempfile
import winreg
import ctypes
import colorsys

# ──────────────────────────────────────────────
# accoreconsole.exe 경로 후보
# ──────────────────────────────────────────────
ACCORECONSOLE_CANDIDATES = [
    r"C:\Program Files\Autodesk\AutoCAD 2018\accoreconsole.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2018 - Korean\accoreconsole.exe",
    r"C:\Program Files (x86)\Autodesk\AutoCAD 2018\accoreconsole.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2026\accoreconsole.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2024\accoreconsole.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2023\accoreconsole.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2022\accoreconsole.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2021\accoreconsole.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2020\accoreconsole.exe",
]

SCALE_OPTIONS_TOP    = ["AA (1:1)", "BB (1:1000)"]
SCALE_OPTIONS_BOTTOM = ["1:1", "1:10", "1:100", "1:1000"]
SCALE_FACTOR_MAP = {
    "AA (1:1)": 1, "BB (1:1000)": 1000,
    "1:1": 1, "1:10": 10, "1:100": 100, "1:1000": 1000,
}
DWG_VERSIONS = ["2018", "2013", "2010", "2007", "2004", "2000", "R14"]

# AutoCAD Color Index 표준 색상 (번호: (hex, 한국어 이름))
ACI_STANDARD = {
    1:  ("#FF0000", "빨강"),
    2:  ("#FFFF00", "노랑"),
    3:  ("#00FF00", "녹색"),
    4:  ("#00FFFF", "청록"),
    5:  ("#0000FF", "파랑"),
    6:  ("#FF00FF", "자홍"),
    7:  ("#FFFFFF", "흰색"),
    8:  ("#414141", "진회색"),
    9:  ("#808080", "회색"),
}

CPU_COUNT = os.cpu_count() or 2
REG_PATH  = r"Software\SHI_AI\SAT2DWG"
_ICO_PATH = os.path.join(tempfile.gettempdir(), "sat2dwg_v2.ico")


# ──────────────────────────────────────────────
# 레지스트리 위치 저장/복원
# ──────────────────────────────────────────────
def reg_load(key):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH) as k:
            return winreg.QueryValueEx(k, key)[0]
    except Exception:
        return None

def reg_save(key, value):
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH) as k:
            winreg.SetValueEx(k, key, 0, winreg.REG_SZ, str(value))
    except Exception:
        pass

def restore_geometry(win, reg_key, default):
    saved = reg_load(reg_key)
    if saved:
        try:
            win.geometry(saved)
            return
        except Exception:
            pass
    win.geometry(default)

def save_geometry(win, reg_key):
    try:
        reg_save(reg_key, win.geometry())
    except Exception:
        pass


# ──────────────────────────────────────────────
# 아이콘 생성 (32×32 아이소메트릭 큐브)
# ──────────────────────────────────────────────
def _make_ico():
    if os.path.exists(_ICO_PATH):
        return
    W = H = 32

    def rgb(r, g, b, a=255):
        return [b, g, r, a]   # BMP BGRA 순서

    BG    = rgb(14, 22, 48)
    TOP   = rgb(155, 205, 255)
    RIGHT = rgb(55, 115, 200)
    LEFT  = rgb(30, 70, 148)
    EDGE  = rgb(225, 242, 255)

    img = [[rgb(14, 22, 48)] * W for _ in range(H)]

    def setp(x, y, c):
        if 0 <= x < W and 0 <= y < H:
            img[y][x] = list(c)

    def fill_poly(verts, color):
        ys = [v[1] for v in verts]
        n  = len(verts)
        for y in range(int(min(ys)), int(max(ys)) + 1):
            xs = []
            for i in range(n):
                ax, ay = verts[i]
                bx, by = verts[(i + 1) % n]
                if ay == by:
                    continue
                lo, hi = (ay, by) if ay < by else (by, ay)
                if lo <= y < hi:
                    t = (y - ay) / (by - ay)
                    xs.append(ax + t * (bx - ax))
            if len(xs) >= 2:
                for x in range(round(min(xs)), round(max(xs)) + 1):
                    setp(x, y, color)

    def draw_line(x0, y0, x1, y1, c):
        dx = abs(x1 - x0); sx = 1 if x0 < x1 else -1
        dy = abs(y1 - y0); sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            setp(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy: err -= dy; x0 += sx
            if e2 <  dx: err += dx; y0 += sy

    # 아이소메트릭 큐브 꼭짓점
    T  = (16,  3)   # 상단
    TR = (26,  9)   # 우상
    TL = ( 6,  9)   # 좌상
    C  = (16, 15)   # 중심 (세 면이 만나는 전면 상단)
    R  = (26, 20)   # 우하
    L  = ( 6, 20)   # 좌하
    B  = (16, 26)   # 하단

    # 면 채우기 (상면, 우면, 좌면)
    fill_poly([T, TR, C, TL], TOP)
    fill_poly([TR, R, B, C],  RIGHT)
    fill_poly([TL, C, B, L],  LEFT)

    # 외곽 육각형 + 내부 3개 꼭짓점선
    edges = [(T, TR), (TR, R), (R, B), (B, L), (L, TL), (TL, T),
             (TR, C), (TL, C), (B, C)]
    for a, b in edges:
        draw_line(*a, *b, EDGE)

    # BMP 직렬화 (하단→상단)
    pixel_bytes = bytearray()
    for y in range(H - 1, -1, -1):
        for x in range(W):
            pixel_bytes.extend(img[y][x])

    and_mask = bytes(4 * H)   # W=32 → 4 bytes/행
    bmp = (struct.pack('<IiiHHIIiiII', 40, W, H * 2, 1, 32, 0, 0, 0, 0, 0, 0)
           + bytes(pixel_bytes) + and_mask)
    ico = (struct.pack('<HHH', 0, 1, 1)
           + struct.pack('<BBBBHHII', W, H, 0, 0, 1, 32, len(bmp), 22)
           + bmp)
    try:
        with open(_ICO_PATH, 'wb') as f:
            f.write(ico)
    except Exception:
        pass

def set_icon(win):
    _make_ico()
    try:
        win.iconbitmap(_ICO_PATH)
    except Exception:
        pass

def remove_minmax_buttons(win):
    """최소화·최대화 버튼 제거 (작업표시줄·아이콘 유지)"""
    def _apply():
        try:
            hwnd  = ctypes.windll.user32.GetParent(win.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
            style &= ~0x00020000  # WS_MINIMIZEBOX
            style &= ~0x00010000  # WS_MAXIMIZEBOX
            ctypes.windll.user32.SetWindowLongW(hwnd, -16, style)
        except Exception:
            pass
    win.after(10, _apply)



# ──────────────────────────────────────────────
# AutoCAD COM 재저장 워커
# ──────────────────────────────────────────────
class AutoCADResaver:
    """AutoCAD COM 인스턴스를 N개 띄워 DWG를 병렬로 재저장한다.
    accoreconsole 스레드와 병행 시작해 초기화 시간을 숨긴다."""

    def __init__(self, log_queue, count=2):
        self.log_queue     = log_queue
        self._count        = count
        self._q            = queue.Queue()
        self._threads      = []
        self._pre_existing = False   # 실행 전 AutoCAD가 이미 열려 있었는지

        # 미리 AutoCAD 실행 여부 확인 (종료 여부 결정에 사용)
        try:
            import win32com.client
            win32com.client.GetActiveObject("AutoCAD.Application")
            self._pre_existing = True
        except Exception:
            pass

        for _ in range(count):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            self._threads.append(t)

    @staticmethod
    def _suppress(acad):
        try: acad.Visible = False
        except Exception: pass
        try: acad.WindowState = 1   # acMinimized
        except Exception: pass

    def _worker(self):
        acad = None
        try:
            import win32com.client
            # DispatchEx → 항상 새 인스턴스 생성 (기존 세션과 분리)
            acad = win32com.client.DispatchEx("AutoCAD.Application")
            self._suppress(acad)
        except Exception as e:
            self.log_queue.put(("err", f"[AutoCAD] 인스턴스 시작 실패: {e}"))

        while True:
            item = self._q.get()
            if item is None:
                # 종료 신호 → 우리가 만든 인스턴스만 Quit
                # (pre_existing이면 DispatchEx로 새로 만든 것이므로 항상 종료)
                if acad:
                    try:
                        acad.Quit()
                    except Exception:
                        pass
                break

            temp_path, final_path, display, on_done = item
            if acad is None:
                on_done("err", display, "AutoCAD 인스턴스 없음")
                continue
            try:
                doc = acad.Documents.Open(temp_path)
                self._suppress(acad)             # 열릴 때 창이 뜨면 재숨김
                doc.SetVariable("ISAVEBAK", 0)   # .bak 생성 억제
                doc.SetVariable("FILEDIA", 0)    # 저장 다이얼로그 억제
                doc.SaveAs(final_path)           # 원본 폴더에 최종 저장
                doc.SetVariable("FILEDIA", 1)
                doc.Close(False)
                _try_remove(temp_path)
                on_done("ok", display, None)
            except Exception as e:
                _try_remove(temp_path)
                on_done("err", display, str(e))

    def submit(self, temp_path, final_path, display, on_done):
        self._q.put((temp_path, final_path, display, on_done))

    def stop(self):
        """각 워커에 종료 신호 전송 후 완료 대기"""
        for _ in range(self._count):
            self._q.put(None)
        for t in self._threads:
            t.join(timeout=30)


class _PipelineCoord:
    """accoreconsole 완료 + AutoCAD 재저장 완료를 조율한다."""

    def __init__(self, log_queue, finish_cb):
        self._lock        = threading.Lock()
        self._pending     = 0          # AutoCAD 재저장 대기 중인 파일 수
        self._accore_done = False
        self._log_queue   = log_queue
        self._finish_cb   = finish_cb

    def accore_submit(self):
        """accoreconsole이 DWG 생성에 성공해 AutoCAD 큐에 올릴 때 호출"""
        with self._lock:
            self._pending += 1

    def on_resave(self, status, display, err_msg):
        """AutoCAD 재저장 콜백"""
        if status == "ok":
            self._log_queue.put(("ok",  f"[완료]    {display}.dwg"))
        else:
            self._log_queue.put(("err", f"[AutoCAD 저장 실패]  {display}.dwg — {err_msg}"))
        with self._lock:
            self._pending -= 1
            self._try_finish()

    def accore_finished(self):
        """모든 accoreconsole 스레드가 끝났을 때 호출"""
        with self._lock:
            self._accore_done = True
            self._try_finish()

    def _try_finish(self):
        if self._accore_done and self._pending == 0:
            self._finish_cb()


# ──────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────
def _try_remove(path):
    try:
        os.remove(path)
    except Exception:
        pass

def find_accoreconsole():
    for path in ACCORECONSOLE_CANDIDATES:
        if os.path.exists(path):
            return path
    return None

def collect_sat_files(folder, include_subfolders):
    if include_subfolders:
        result = []
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(".sat"):
                    result.append(os.path.join(root, f))
        return result
    return glob.glob(os.path.join(folder, "*.sat"))

def aci_to_hex(num):
    """AutoCAD ACI 번호 → 근사 hex 색상 (10-249는 HSV 보간)"""
    if num in ACI_STANDARD:
        return ACI_STANDARD[num][0]
    if 250 <= num <= 255:
        v = int(50 + (num - 250) / 5 * 200)
        return f"#{v:02X}{v:02X}{v:02X}"
    if 10 <= num <= 249:
        idx = num - 10
        hue_idx = idx // 10          # 0-23: 24가지 색상
        pos     = idx % 10           # 0-9: 밝기/채도 단계
        hue     = hue_idx / 24.0
        if pos < 5:
            # 0→풀컬러, 4→연한색 (채도 감소)
            s_list = [1.0, 0.75, 0.5, 0.25, 0.1]
            s, v = s_list[pos], 1.0
        else:
            # 5→어두운색, 9→매우 어두운색 (명도 감소)
            v_list = [0.75, 0.5, 0.25, 0.12, 0.05]
            s, v = 1.0, v_list[pos - 5]
        r, g, b = colorsys.hsv_to_rgb(hue, s, v)
        return f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"
    return "#888888"

def sanitize_layer_name(name):
    for ch in r'<>/\"|:;?*=,`':
        name = name.replace(ch, "_")
    return name[:255]

def build_script(sat_path, dwg_path, options):
    scale_factor = SCALE_FACTOR_MAP.get(options["scale"], 1)
    use_layer    = options["auto_layer"]
    dwg_version  = options["dwg_version"]
    layer_name   = sanitize_layer_name(
        os.path.splitext(os.path.basename(sat_path))[0]
    )
    solid_color_aci = options.get("solid_color_aci")   # int(1-255) or None
    solid_color_rgb = options.get("solid_color_rgb")   # (r,g,b) or None

    def _color_args():
        """CHPROP 색상 인자 목록 반환"""
        if solid_color_aci is not None:
            return ["C", str(solid_color_aci)]
        if solid_color_rgb is not None:
            r, g, b = solid_color_rgb
            # AutoCAD TrueColor: C → t(ruecolor) → R,G,B
            return ["C", "t", f"{r},{g},{b}"]
        return []

    has_color = solid_color_aci is not None or solid_color_rgb is not None

    lines = []
    if use_layer:
        lines += ["-LAYER", "M", layer_name, ""]
    lines.append(f'_ACISIN "{sat_path}"')

    # 레이어·색상 동시 적용 (CHPROP 한 번으로 처리)
    if use_layer and has_color:
        lines += ["_CHPROP", "_all", "", "LA", layer_name] + _color_args() + [""]
    elif use_layer:
        lines += ["_CHPROP", "_all", "", "LA", layer_name, ""]
    elif has_color:
        lines += ["_CHPROP", "_all", ""] + _color_args() + [""]

    if scale_factor != 1:
        lines += ["_SCALE", "_all", "", "0,0,0", str(scale_factor)]

    # 모든 수정 완료 후 레이어 잠금 (LOck)
    if use_layer:
        lines += ["-LAYER", "LO", layer_name, ""]

    # 저장 전 전체 보기 (Zoom Extents)
    lines += ["_ZOOM", "_E"]

    lines += ["_SAVEAS", dwg_version, f'"{dwg_path}"', "_QUIT Y", ""]
    return "\n".join(lines)


# ──────────────────────────────────────────────
# 단일 파일 변환
# ──────────────────────────────────────────────
def convert_single(accoreconsole_path, sat_path, base_folder, log_queue, options, stop_event):
    if stop_event.is_set():
        return "cancelled"

    base_name  = os.path.splitext(os.path.basename(sat_path))[0]
    folder     = os.path.dirname(sat_path)
    final_path = os.path.join(folder, base_name + ".dwg")

    # 임시 경로 (accoreconsole은 temp에 저장 → AutoCAD가 최종 경로로 SaveAs)
    temp_path  = os.path.join(
        tempfile.gettempdir(),
        f"sat2dwg_{base_name}_{os.urandom(4).hex()}.dwg"
    )

    try:
        rel = os.path.relpath(sat_path, base_folder)
    except ValueError:
        rel = os.path.basename(sat_path)
    display = os.path.splitext(rel)[0]

    if options["skip_existing"] and os.path.exists(final_path):
        log_queue.put(("skip", f"[건너뜀]  {display}.dwg"))
        return "skip"

    script = build_script(sat_path, temp_path, options)

    try:
        subprocess.run(
            [accoreconsole_path, "/nologo", "/nohardware", "/p", "<<AutoCAD Defaults>>"],
            input=script.encode("cp949", errors="replace"),
            capture_output=True,
            timeout=options.get("timeout", 60),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if os.path.exists(temp_path):
            # accore 성공 → AutoCAD 재저장 대기 (로그는 재저장 완료 후 출력)
            return ("pending", temp_path, final_path, display)
        else:
            log_queue.put(("err", f"[실패]    {display}.sat  —  DWG 파일 미생성"))
            return ("err",)
    except subprocess.TimeoutExpired:
        _try_remove(temp_path)
        log_queue.put(("err", f"[시간초과]  {display}.sat  ({options.get('timeout', 60)}초 초과)"))
        return ("err",)
    except Exception as e:
        _try_remove(temp_path)
        log_queue.put(("err", f"[오류]    {display}.sat  —  {e}"))
        return ("err",)


# ──────────────────────────────────────────────
# 로그 창
# ──────────────────────────────────────────────
class LogWindow:
    def __init__(self, root, total, options, folder):
        self.root    = root
        self.total   = total
        self.options = options
        self.folder  = folder
        self.done = self.ok = self.fail = self.skip = 0
        self.log_queue = queue.Queue()

        root.title("SAT → DWG 변환 중...")
        set_icon(root)
        restore_geometry(root, "log_geometry", "680x560")
        root.resizable(True, True)
        root.protocol("WM_DELETE_WINDOW", lambda: None)
        remove_minmax_buttons(root)

        # ── 상태 영역 ────────────────────────────
        stat_frame = tk.Frame(root)
        stat_frame.pack(fill="x", padx=10, pady=(8, 2))

        # 1행: 아이콘 + 상태 텍스트  /  오른쪽: n / total
        top_row = tk.Frame(stat_frame)
        top_row.pack(fill="x")

        self._icon_lbl = tk.Label(top_row, text="⏳", font=("Segoe UI Emoji", 13))
        self._icon_lbl.pack(side="left", padx=(0, 6))

        self._status_var = tk.StringVar(value="변환 중...")
        tk.Label(top_row, textvariable=self._status_var,
                 font=("맑은 고딕", 11, "bold"), anchor="w").pack(side="left")

        self._progress_var = tk.StringVar(value=f"0 / {total}")
        tk.Label(top_row, textvariable=self._progress_var,
                 font=("맑은 고딕", 11, "bold"), anchor="e").pack(side="right")

        # 2행: 카운터 칸
        cnt_row = tk.Frame(stat_frame)
        cnt_row.pack(anchor="w", pady=(5, 0))

        def _counter_cell(parent, icon, label, color):
            f = tk.Frame(parent, padx=8, pady=3)
            f.pack(side="left", padx=(0, 24))
            tk.Label(f, text=icon, font=("Segoe UI Emoji", 10)).pack(side="left")
            tk.Label(f, text=f" {label}", font=("맑은 고딕", 9)).pack(side="left")
            var = tk.StringVar(value="0")
            tk.Label(f, textvariable=var, font=("Consolas", 11, "bold"),
                     fg=color, width=4, anchor="e").pack(side="left")
            return var

        self._ok_var   = _counter_cell(cnt_row, "✔", "완료",   "#4caf50")
        self._fail_var = _counter_cell(cnt_row, "✖", "실패",   "#e53935")
        self._skip_var = _counter_cell(cnt_row, "⏭", "건너뜀", "#f9a825")

        # 프로그레스바
        self.canvas = tk.Canvas(root, height=13, bg="#dde3ed", highlightthickness=0)
        self.canvas.pack(fill="x", padx=8, pady=(4, 2))
        self.bar = self.canvas.create_rectangle(0, 0, 0, 13, fill="#4caf50", width=0)

        # 로그 텍스트
        self.text = scrolledtext.ScrolledText(
            root, font=("Consolas", 9),
            state="disabled", bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white"
        )
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 2))
        self.text.tag_config("ok",   foreground="#6adc6a")
        self.text.tag_config("err",  foreground="#f97070")
        self.text.tag_config("skip", foreground="#c8b400")
        self.text.tag_config("info", foreground="#9cdcfe")

        self.close_btn = tk.Button(
            root, text="닫기", state="disabled", width=10,
            command=self._on_close
        )
        self.close_btn.pack(pady=(0, 6))

    def _on_close(self):
        save_geometry(self.root, "log_geometry")
        self.root.destroy()

    def append(self, tag, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.text.configure(state="normal")
        self.text.insert("end", f"[{ts}]  {msg}\n", tag)
        self.text.see("end")
        self.text.configure(state="disabled")

    def update_progress(self):
        self.done += 1
        pct = self.done / self.total if self.total else 1
        self.canvas.update_idletasks()
        w = self.canvas.winfo_width()
        self.canvas.coords(self.bar, 0, 0, int(w * pct), 13)
        self._progress_var.set(f"{self.done} / {self.total}")
        self._ok_var.set(str(self.ok))
        self._fail_var.set(str(self.fail))
        self._skip_var.set(str(self.skip))

    def finish(self):
        if self.fail > 0:
            self._icon_lbl.config(text="⚠️")
            self._status_var.set("변환 완료 (일부 실패)")
        elif self.ok == 0:
            self._icon_lbl.config(text="⏭")
            self._status_var.set("모두 건너뜀")
        else:
            self._icon_lbl.config(text="✅")
            self._status_var.set("변환 완료")
        self._progress_var.set(f"{self.total} / {self.total}")
        self._ok_var.set(str(self.ok))
        self._fail_var.set(str(self.fail))
        self._skip_var.set(str(self.skip))
        self.root.title("SAT → DWG 변환 완료")
        self.close_btn.configure(state="normal")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def poll_queue(self):
        try:
            while True:
                tag, msg = self.log_queue.get_nowait()
                self.append(tag, msg)
                if tag == "ok":
                    self.ok += 1;   self.update_progress()
                elif tag == "err":
                    self.fail += 1; self.update_progress()
                elif tag == "skip":
                    self.skip += 1; self.update_progress()
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queue)


# ──────────────────────────────────────────────
# 변환 스레드
# ──────────────────────────────────────────────
def run_conversion(accoreconsole_path, sat_files, base_folder, log_win, options):
    workers    = min(options["workers"], len(sat_files))
    stop_event = threading.Event()

    acad_count = options.get("acad_instances", 2)

    log_win.log_queue.put((
        "info",
        f"스케일 : {options['scale']}   /   DWG 버전 : {options['dwg_version']}"
        f"   /   파일 {len(sat_files)}개   /   동시 처리 {workers}코어"
        f"   /   AutoCAD {acad_count}개\n"
    ))

    # ── AutoCAD 재저장 워커를 accoreconsole과 동시에 시작 (초기화 시간 숨김)
    resaver = AutoCADResaver(log_win.log_queue, count=acad_count)

    def _finish_cb():
        log_win.root.after(0, log_win.finish)
        # 모든 작업 완료 후 AutoCAD 인스턴스 종료 (백그라운드 스레드에서)
        threading.Thread(target=resaver.stop, daemon=True).start()

    coord = _PipelineCoord(log_win.log_queue, finish_cb=_finish_cb)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                convert_single, accoreconsole_path, f, base_folder,
                log_win.log_queue, options, stop_event
            ): f
            for f in sat_files
        }
        for future in as_completed(futures):
            if stop_event.is_set():
                break
            result = future.result()
            tag = result[0] if isinstance(result, tuple) else result
            if tag == "pending":
                _, temp_path, final_path, display = result
                coord.accore_submit()
                resaver.submit(temp_path, final_path, display, coord.on_resave)
            elif tag == "err" and options.get("stop_on_error"):
                stop_event.set()
                log_win.log_queue.put(("err", "[중단]  오류 발생으로 나머지 변환을 중단합니다."))

    coord.accore_finished()


# ──────────────────────────────────────────────
# 옵션 창
# ──────────────────────────────────────────────
class OptionsDialog:
    def __init__(self, parent):
        self.result       = None
        self._workers_val = CPU_COUNT   # 기본 = 최대

        self.dlg = tk.Toplevel(parent)
        self.dlg.title("SAT → DWG 변환 옵션")
        self.dlg.resizable(False, True)
        self.dlg.grab_set()
        set_icon(self.dlg)
        restore_geometry(self.dlg, "opt_geometry_v2", "460x580")
        self.dlg.minsize(460, 560)
        self.dlg.protocol("WM_DELETE_WINDOW", self._cancel)
        remove_minmax_buttons(self.dlg)

        P = dict(padx=10, pady=3)

        # ── 스케일 ──────────────────────────────
        sf = tk.LabelFrame(self.dlg, text=" 스케일 ", font=("", 9, "bold"), padx=6, pady=3)
        sf.pack(fill="x", **P)
        self.scale_var = tk.StringVar(value="1:1")
        row_top = tk.Frame(sf); row_top.pack(fill="x")
        for lbl in SCALE_OPTIONS_TOP:
            tk.Radiobutton(row_top, text=lbl, variable=self.scale_var,
                           value=lbl).pack(side="left", padx=8)
        ttk.Separator(sf, orient="horizontal").pack(fill="x", pady=2)
        row_bot = tk.Frame(sf); row_bot.pack(fill="x")
        for lbl in SCALE_OPTIONS_BOTTOM:
            tk.Radiobutton(row_bot, text=lbl, variable=self.scale_var,
                           value=lbl).pack(side="left", padx=6)

        # ── 변환 옵션 ────────────────────────────
        cf = tk.LabelFrame(self.dlg, text=" 변환 옵션 ", font=("", 9, "bold"), padx=6, pady=3)
        cf.pack(fill="x", **P)
        self.auto_layer_var = tk.BooleanVar(value=True)
        tk.Checkbutton(cf, text="레이어 자동변환 (파일명 기준)",
                       variable=self.auto_layer_var).pack(anchor="w")
        self.skip_existing_var = tk.BooleanVar(value=True)
        tk.Checkbutton(cf, text="중복 무시 (동일 DWG 이미 존재 시 건너뜀)",
                       variable=self.skip_existing_var).pack(anchor="w")
        self.include_subfolders_var = tk.BooleanVar(value=False)
        tk.Checkbutton(cf, text="하부폴더 포함 (하위 폴더의 SAT 파일까지 변환)",
                       variable=self.include_subfolders_var).pack(anchor="w")

        # ── 3D 솔리드 색상 ──────────────────────────
        xf = tk.LabelFrame(self.dlg, text=" 3D 솔리드 색상 ", font=("", 9, "bold"), padx=6, pady=4)
        xf.pack(fill="x", **P)

        self.use_color_var  = tk.BooleanVar(value=True)
        self.color_mode_var = tk.StringVar(value="aci")   # "aci" or "rgb"
        self.color_num_var  = tk.IntVar(value=60)
        self._rgb_vals      = [tk.IntVar(value=255), tk.IntVar(value=0), tk.IntVar(value=0)]

        # 활성화 체크 + 모드 라디오
        top_row = tk.Frame(xf); top_row.pack(fill="x")
        tk.Checkbutton(top_row, text="색상 변환 적용 (모든 3D 솔리드)",
                       variable=self.use_color_var,
                       command=self._toggle_color).pack(side="left")
        tk.Radiobutton(top_row, text="ACI", variable=self.color_mode_var,
                       value="aci", command=self._switch_color_mode).pack(side="left", padx=(12, 2))
        tk.Radiobutton(top_row, text="트루컬러", variable=self.color_mode_var,
                       value="rgb", command=self._switch_color_mode).pack(side="left")

        # ── ACI 패널 ──
        self._aci_frame = tk.Frame(xf)
        self._aci_frame.pack(fill="x", pady=(2, 0))

        # 표준 색상 버튼 1–9 + 구분 후 60번
        std_row = tk.Frame(self._aci_frame); std_row.pack(anchor="w")
        tk.Label(std_row, text="표준색:", font=("", 8)).pack(side="left")
        self._std_btns = []
        for num in range(1, 10):
            hex_c, _ = ACI_STANDARD[num]
            relief = "groove" if num == 7 else "raised"
            btn = tk.Button(
                std_row, bg=hex_c, width=2, height=1,
                relief=relief, bd=2, cursor="hand2",
                command=lambda n=num: self._set_aci_color(n),
            )
            btn.pack(side="left", padx=1)
            self._std_btns.append(btn)
        # 구분선 + 60번 버튼
        tk.Frame(std_row, width=1, bg="#aaaaaa").pack(side="left", fill="y", padx=(6, 5))
        hex_60 = aci_to_hex(60)
        btn60 = tk.Button(
            std_row, bg=hex_60, width=2, height=1,
            relief="raised", bd=2, cursor="hand2",
            command=lambda: self._set_aci_color(60),
        )
        btn60.pack(side="left", padx=1)
        tk.Label(std_row, text="60", font=("", 7), fg="gray").pack(side="left", padx=(1, 0))
        self._std_btns.append(btn60)

        # 번호 스핀박스 + 미리보기
        spin_row = tk.Frame(self._aci_frame); spin_row.pack(anchor="w", pady=(3, 0))
        tk.Label(spin_row, text="번호 (1-255):", font=("", 8)).pack(side="left")
        self._color_spin = tk.Spinbox(
            spin_row, from_=1, to=255, textvariable=self.color_num_var,
            width=5, command=self._update_aci_preview,
        )
        self._color_spin.pack(side="left", padx=3)
        self._color_spin.bind("<KeyRelease>", lambda e: self._update_aci_preview())

        self._aci_swatch = tk.Canvas(spin_row, width=26, height=18, bd=1, relief="sunken",
                                     highlightthickness=0)
        self._aci_swatch.pack(side="left")
        self._aci_swatch_rect = self._aci_swatch.create_rectangle(0, 0, 26, 18,
                                                                    fill="#FFFFFF", outline="")
        self._aci_name_var = tk.StringVar(value="")
        tk.Label(spin_row, textvariable=self._aci_name_var,
                 fg="gray", font=("", 8), width=12, anchor="w").pack(side="left", padx=4)

        # ── 트루컬러 패널 ──
        self._rgb_frame = tk.Frame(xf)
        # (pack은 _switch_color_mode에서 제어)

        rgb_labels = ["R", "G", "B"]
        rgb_defaults = [255, 0, 0]
        self._rgb_spins = []
        for i, (lbl, dv) in enumerate(zip(rgb_labels, rgb_defaults)):
            self._rgb_vals[i].set(dv)
            rr = tk.Frame(self._rgb_frame); rr.pack(side="left", padx=(0, 8))
            tk.Label(rr, text=f"{lbl}:", font=("", 8)).pack(side="left")
            sp = tk.Spinbox(rr, from_=0, to=255, textvariable=self._rgb_vals[i],
                            width=4, command=self._update_rgb_preview)
            sp.pack(side="left", padx=2)
            sp.bind("<KeyRelease>", lambda e: self._update_rgb_preview())
            self._rgb_spins.append(sp)

        self._rgb_swatch = tk.Canvas(self._rgb_frame, width=26, height=18, bd=1,
                                      relief="sunken", highlightthickness=0)
        self._rgb_swatch.pack(side="left", padx=4)
        self._rgb_swatch_rect = self._rgb_swatch.create_rectangle(0, 0, 26, 18,
                                                                    fill="#FF0000", outline="")
        tk.Button(self._rgb_frame, text="색상 선택...", font=("", 8),
                  command=self._pick_rgb_color).pack(side="left", padx=4)

        # 초기화
        self._all_color_widgets = (
            [self._color_spin, self._aci_swatch]
            + self._std_btns + self._rgb_spins + [self._rgb_swatch]
        )
        self._toggle_color()
        self._switch_color_mode()
        self._update_aci_preview()
        self._update_rgb_preview()

        # ── DWG 버전 ─────────────────────────────
        vf = tk.LabelFrame(self.dlg, text=" DWG 저장 버전 ", font=("", 9, "bold"), padx=6, pady=3)
        vf.pack(fill="x", **P)
        vr = tk.Frame(vf); vr.pack(anchor="w")
        self.dwg_version_var = tk.StringVar(value="2018")
        ttk.Combobox(vr, textvariable=self.dwg_version_var,
                     values=DWG_VERSIONS, state="readonly", width=8).pack(side="left")
        tk.Label(vr, text="(권장: 2018)", fg="gray", font=("", 8)).pack(side="left", padx=4)

        # ── 고급 옵션 ────────────────────────────
        af = tk.LabelFrame(self.dlg, text=" 고급 옵션 ", font=("", 9, "bold"), padx=6, pady=3)
        af.pack(fill="x", **P)

        # AutoCAD 인스턴스 수
        ra = tk.Frame(af); ra.pack(fill="x", pady=2)
        tk.Label(ra, text="AutoCAD 인스턴스 수:").pack(side="left")
        self.acad_instances_var = tk.IntVar(value=2)
        tk.Spinbox(ra, from_=1, to=4, textvariable=self.acad_instances_var,
                   width=3).pack(side="left", padx=3)
        tk.Label(ra, text="(많을수록 재저장 빠름, 메모리 주의)",
                 fg="gray", font=("", 8)).pack(side="left", padx=4)

        # 코어 수 — 일반 Label + ▲▼ 버튼
        r1 = tk.Frame(af); r1.pack(fill="x", pady=2)
        tk.Label(r1, text="동시 처리 코어 수:").pack(side="left")
        self._workers_disp = tk.StringVar(value="최대")
        tk.Label(r1, textvariable=self._workers_disp,
                 width=4, anchor="w", font=("", 9)).pack(side="left", padx=3)
        tk.Button(r1, text="▲", width=2, pady=0,
                  command=self._inc_workers).pack(side="left")
        tk.Button(r1, text="▼", width=2, pady=0,
                  command=self._dec_workers).pack(side="left")
        tk.Label(r1, text=f"(최대 {CPU_COUNT}코어)",
                 fg="gray", font=("", 8)).pack(side="left", padx=4)

        # 제한 시간
        r2 = tk.Frame(af); r2.pack(fill="x", pady=2)
        tk.Label(r2, text="파일당 제한 시간:").pack(side="left")
        self.timeout_var = tk.IntVar(value=60)
        tk.Spinbox(r2, from_=10, to=3600, increment=10,
                   textvariable=self.timeout_var, width=6).pack(side="left", padx=3)
        tk.Label(r2, text="초", fg="gray", font=("", 8)).pack(side="left")

        # 오류 시 중단
        self.stop_on_error_var = tk.BooleanVar(value=False)
        tk.Checkbutton(af, text="오류 발생 시 즉시 중단 (나머지 파일 처리 취소)",
                       variable=self.stop_on_error_var).pack(anchor="w", pady=(2, 0))

        # ── 버튼 ─────────────────────────────────
        btn_row = tk.Frame(self.dlg); btn_row.pack(pady=8)
        tk.Button(btn_row, text="폴더 선택 후 변환 시작", width=18,
                  font=("", 9, "bold"), bg="#4caf50", fg="white",
                  command=self._ok).pack(side="left", padx=6)
        tk.Button(btn_row, text="취소", width=8,
                  command=self._cancel).pack(side="left", padx=6)

    def _toggle_color(self):
        """색상 변환 체크 여부에 따라 모든 색상 위젯 활성/비활성"""
        enabled = self.use_color_var.get()
        # 모드 라디오 버튼은 enabled 상태로만 동작; 서브 프레임 내 위젯 제어
        for w in self._all_color_widgets:
            try:
                w.config(state="normal" if enabled else "disabled")
            except tk.TclError:
                pass

    def _switch_color_mode(self):
        """ACI ↔ 트루컬러 패널 전환"""
        if self.color_mode_var.get() == "aci":
            self._rgb_frame.pack_forget()
            self._aci_frame.pack(fill="x", pady=(2, 0))
        else:
            self._aci_frame.pack_forget()
            self._rgb_frame.pack(fill="x", pady=(2, 0))

    def _set_aci_color(self, num):
        self.color_num_var.set(num)
        self._update_aci_preview()

    def _update_aci_preview(self):
        try:
            num = max(1, min(255, int(self.color_num_var.get())))
        except (ValueError, tk.TclError):
            return
        hex_c = aci_to_hex(num)
        self._aci_swatch.itemconfig(self._aci_swatch_rect, fill=hex_c)
        if num in ACI_STANDARD:
            self._aci_name_var.set(ACI_STANDARD[num][1])
        elif 250 <= num <= 255:
            self._aci_name_var.set("회색 계열")
        else:
            self._aci_name_var.set(f"ACI {num}")

    def _update_rgb_preview(self):
        try:
            r = max(0, min(255, int(self._rgb_vals[0].get())))
            g = max(0, min(255, int(self._rgb_vals[1].get())))
            b = max(0, min(255, int(self._rgb_vals[2].get())))
        except (ValueError, tk.TclError):
            return
        hex_c = f"#{r:02X}{g:02X}{b:02X}"
        self._rgb_swatch.itemconfig(self._rgb_swatch_rect, fill=hex_c)

    def _pick_rgb_color(self):
        """tkinter 색상 선택 다이얼로그"""
        try:
            r = int(self._rgb_vals[0].get())
            g = int(self._rgb_vals[1].get())
            b = int(self._rgb_vals[2].get())
        except (ValueError, tk.TclError):
            r, g, b = 255, 0, 0
        init_color = f"#{r:02X}{g:02X}{b:02X}"
        result = colorchooser.askcolor(color=init_color, parent=self.dlg, title="트루컬러 선택")
        if result and result[0]:
            nr, ng, nb = (int(v) for v in result[0])
            self._rgb_vals[0].set(nr)
            self._rgb_vals[1].set(ng)
            self._rgb_vals[2].set(nb)
            self._update_rgb_preview()

    def _inc_workers(self):
        if self._workers_val < CPU_COUNT:
            self._workers_val += 1
        self._workers_disp.set(
            "최대" if self._workers_val >= CPU_COUNT else str(self._workers_val)
        )

    def _dec_workers(self):
        if self._workers_val > 1:
            self._workers_val -= 1
        self._workers_disp.set(str(self._workers_val))

    def _ok(self):
        save_geometry(self.dlg, "opt_geometry_v2")
        solid_color_aci = None
        solid_color_rgb = None
        if self.use_color_var.get():
            if self.color_mode_var.get() == "aci":
                try:
                    solid_color_aci = max(1, min(255, int(self.color_num_var.get())))
                except (ValueError, tk.TclError):
                    pass
            else:
                try:
                    r = max(0, min(255, int(self._rgb_vals[0].get())))
                    g = max(0, min(255, int(self._rgb_vals[1].get())))
                    b = max(0, min(255, int(self._rgb_vals[2].get())))
                    solid_color_rgb = (r, g, b)
                except (ValueError, tk.TclError):
                    pass
        self.result = {
            "scale":              self.scale_var.get(),
            "auto_layer":         self.auto_layer_var.get(),
            "skip_existing":      self.skip_existing_var.get(),
            "include_subfolders": self.include_subfolders_var.get(),
            "dwg_version":        self.dwg_version_var.get(),
            "workers":            self._workers_val,
            "acad_instances":     max(1, min(4, self.acad_instances_var.get())),
            "timeout":            self.timeout_var.get(),
            "stop_on_error":      self.stop_on_error_var.get(),
            "solid_color_aci":    solid_color_aci,
            "solid_color_rgb":    solid_color_rgb,
        }
        self.dlg.destroy()

    def _cancel(self):
        save_geometry(self.dlg, "opt_geometry_v2")
        self.dlg.destroy()

    def show(self):
        self.dlg.wait_window()
        return self.result


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
def main():
    root_hidden = tk.Tk()
    root_hidden.withdraw()
    set_icon(root_hidden)

    # 1) accoreconsole 탐색
    accoreconsole_path = find_accoreconsole()

    # 2) 옵션 창
    options = OptionsDialog(root_hidden).show()
    if options is None:
        root_hidden.destroy()
        return

    if not accoreconsole_path:
        messagebox.showerror(
            "accoreconsole 없음",
            "accoreconsole.exe를 찾을 수 없습니다.\n"
            "sat_to_dwg.py 상단 ACCORECONSOLE_CANDIDATES 목록에\n"
            "설치된 경로를 직접 추가해 주세요."
        )
        root_hidden.destroy()
        return

    # 3) 폴더 선택
    from tkinter import filedialog
    folder = filedialog.askdirectory(
        title="SAT 파일이 있는 폴더를 선택하세요",
        parent=root_hidden,
    )
    if not folder:
        root_hidden.destroy()
        return

    # 4) SAT 파일 수집
    sat_files = collect_sat_files(folder, options["include_subfolders"])
    if not sat_files:
        scope = "선택한 폴더(및 하위 폴더)" if options["include_subfolders"] else "선택한 폴더"
        messagebox.showwarning("파일 없음", f"{scope}에 SAT 파일이 없습니다.\n{folder}")
        root_hidden.destroy()
        return

    root_hidden.destroy()

    # 5) 로그 창 + 변환 시작
    log_root = tk.Tk()
    log_win  = LogWindow(log_root, total=len(sat_files), options=options, folder=folder)
    log_root.lift()
    log_root.attributes("-topmost", True)
    log_root.after(200, lambda: log_root.attributes("-topmost", False))
    log_root.after(100, log_win.poll_queue)

    threading.Thread(
        target=run_conversion,
        args=(accoreconsole_path, sat_files, folder, log_win, options),
        daemon=True,
    ).start()

    log_root.mainloop()


if __name__ == "__main__":
    main()
