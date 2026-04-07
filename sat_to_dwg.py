import os
import glob
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import datetime
import struct
import tempfile
import winreg

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

SCALE_OPTIONS_TOP    = ["AA (1:1)", "BB (1:100)"]
SCALE_OPTIONS_BOTTOM = ["1:1", "1:10", "1:100", "1:1000"]
SCALE_FACTOR_MAP = {
    "AA (1:1)": 1, "BB (1:100)": 100,
    "1:1": 1, "1:10": 10, "1:100": 100, "1:1000": 1000,
}
DWG_VERSIONS = ["2018", "2013", "2010", "2007", "2004", "2000", "R14"]

CPU_COUNT = os.cpu_count() or 2
REG_PATH  = r"Software\SHI_AI\SAT2DWG"
_ICO_PATH = os.path.join(tempfile.gettempdir(), "sat2dwg_app.ico")


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
# 아이콘 생성 (CAD 테마 16×16 ICO)
# ──────────────────────────────────────────────
def _make_ico():
    if os.path.exists(_ICO_PATH):
        return
    W, H = 16, 16
    pixels = []
    for y in range(H - 1, -1, -1):   # ICO는 bottom-up
        for x in range(W):
            b, g, r, a = 45, 65, 105, 255          # 기본 남색
            if x in (0, W-1) or y in (0, H-1):
                b, g, r, a = 110, 150, 210, 255    # 테두리
            elif y in (3, 7, 11) and 2 <= x <= 13:
                b, g, r, a = 210, 230, 255, 255    # 가로 선 3개
            elif x == 2 and 2 <= y <= 13:
                b, g, r, a = 140, 180, 240, 255    # 세로 악센트
            pixels.extend([b, g, r, a])
    pixel_data = bytes(pixels)
    and_mask   = bytes([0] * (4 * H))
    bmp = struct.pack('<IiiHHIIiiII', 40, W, H * 2, 1, 32, 0, 0, 0, 0, 0, 0) \
          + pixel_data + and_mask
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


# ──────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────
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
    lines = []
    if use_layer:
        lines += ["-LAYER", "M", layer_name, ""]
    lines.append(f'_ACISIN "{sat_path}"')
    if use_layer:
        lines += ["_CHPROP", "_all", "", "LA", layer_name, ""]
    if scale_factor != 1:
        lines += ["_SCALE", "_all", "", "0,0,0", str(scale_factor)]
    lines += ["_SAVEAS", dwg_version, f'"{dwg_path}"', "_QUIT Y", ""]
    return "\n".join(lines)


# ──────────────────────────────────────────────
# 단일 파일 변환
# ──────────────────────────────────────────────
def convert_single(accoreconsole_path, sat_path, base_folder, log_queue, options, stop_event):
    if stop_event.is_set():
        return "cancelled"

    base_name = os.path.splitext(os.path.basename(sat_path))[0]
    folder    = os.path.dirname(sat_path)
    dwg_path  = os.path.join(folder, base_name + ".dwg")

    # 하부폴더 파일은 경로 포함 표시
    try:
        rel = os.path.relpath(sat_path, base_folder)
    except ValueError:
        rel = os.path.basename(sat_path)
    display = os.path.splitext(rel)[0]

    if options["skip_existing"] and os.path.exists(dwg_path):
        log_queue.put(("skip", f"[건너뜀]  {display}.dwg"))
        return "skip"

    script = build_script(sat_path, dwg_path, options)

    try:
        subprocess.run(
            [accoreconsole_path, "/nologo", "/nohardware", "/p", "<<AutoCAD Defaults>>"],
            input=script.encode("cp949", errors="replace"),
            capture_output=True,
            timeout=options.get("timeout", 60),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if os.path.exists(dwg_path):
            log_queue.put(("ok", f"[완료]    {display}.dwg"))
            return "ok"
        else:
            log_queue.put(("err", f"[실패]    {display}.sat  —  DWG 파일 미생성"))
            return "err"

    except subprocess.TimeoutExpired:
        log_queue.put(("err", f"[시간초과]  {display}.sat  ({options.get('timeout', 60)}초 초과)"))
        return "err"
    except Exception as e:
        log_queue.put(("err", f"[오류]    {display}.sat  —  {e}"))
        return "err"


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
        restore_geometry(root, "log_geometry", "640x580")
        root.resizable(True, True)
        root.protocol("WM_DELETE_WINDOW", lambda: None)

        # 상태 표시줄 (크고 넓게)
        self.status_var = tk.StringVar(
            value=f"변환 중 ...          ( 0 / {total} )          완료  0          실패  0          건너뜀  0"
        )
        tk.Label(root, textvariable=self.status_var, anchor="w",
                 font=("Consolas", 11, "bold")).pack(fill="x", padx=8, pady=(6, 2))

        # 프로그레스바
        self.canvas = tk.Canvas(root, height=14, bg="#dde3ed", highlightthickness=0)
        self.canvas.pack(fill="x", padx=8, pady=(0, 3))
        self.bar = self.canvas.create_rectangle(0, 0, 0, 14, fill="#4caf50", width=0)

        # 로그 텍스트
        self.text = scrolledtext.ScrolledText(
            root, font=("Consolas", 9),
            state="disabled", bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white"
        )
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 3))
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
        self.canvas.coords(self.bar, 0, 0, int(w * pct), 14)
        self.status_var.set(
            f"변환 중 ...          ( {self.done} / {self.total} )"
            f"          완료  {self.ok}"
            f"          실패  {self.fail}"
            f"          건너뜀  {self.skip}"
        )

    def finish(self):
        self.status_var.set(
            f"완료 !          성공  {self.ok} 개"
            f"          실패  {self.fail} 개"
            f"          건너뜀  {self.skip} 개"
            f"          전체  {self.total} 개"
        )
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

    log_win.log_queue.put((
        "info",
        f"스케일 : {options['scale']}   /   DWG 버전 : {options['dwg_version']}"
        f"   /   파일 {len(sat_files)}개   /   동시 처리 {workers}코어\n"
    ))

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
            if options.get("stop_on_error") and future.result() == "err":
                stop_event.set()
                log_win.log_queue.put(("err", "[중단]  오류 발생으로 나머지 변환을 중단합니다."))

    log_win.root.after(0, log_win.finish)


# ──────────────────────────────────────────────
# 옵션 창
# ──────────────────────────────────────────────
class OptionsDialog:
    def __init__(self, parent):
        self.result       = None
        self._workers_val = CPU_COUNT

        self.dlg = tk.Toplevel(parent)
        self.dlg.title("SAT → DWG 변환 옵션")
        self.dlg.resizable(False, False)
        self.dlg.grab_set()
        set_icon(self.dlg)
        restore_geometry(self.dlg, "opt_geometry", "460x450")
        self.dlg.protocol("WM_DELETE_WINDOW", self._cancel)

        P = dict(padx=10, pady=3)

        # ── 스케일 ──────────────────────────────
        sf = tk.LabelFrame(self.dlg, text=" 스케일 ", font=("", 9, "bold"), padx=6, pady=3)
        sf.pack(fill="x", **P)
        self.scale_var = tk.StringVar(value="1:1")
        row_top = tk.Frame(sf); row_top.pack(fill="x")
        for lbl in SCALE_OPTIONS_TOP:
            tk.Radiobutton(row_top, text=lbl, variable=self.scale_var, value=lbl).pack(side="left", padx=8)
        ttk.Separator(sf, orient="horizontal").pack(fill="x", pady=2)
        row_bot = tk.Frame(sf); row_bot.pack(fill="x")
        for lbl in SCALE_OPTIONS_BOTTOM:
            tk.Radiobutton(row_bot, text=lbl, variable=self.scale_var, value=lbl).pack(side="left", padx=6)

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

        # 코어 수 — '최대' 기본, ▼ 누르면 숫자
        r1 = tk.Frame(af); r1.pack(fill="x", pady=2)
        tk.Label(r1, text="동시 처리 코어 수:").pack(side="left")
        self._workers_disp = tk.StringVar(value="최대")
        tk.Label(r1, textvariable=self._workers_disp, width=5,
                 font=("Consolas", 9, "bold"), relief="sunken",
                 bg="white", anchor="center").pack(side="left", padx=3)
        tk.Button(r1, text="▲", width=2, command=self._inc_workers).pack(side="left")
        tk.Button(r1, text="▼", width=2, command=self._dec_workers).pack(side="left")
        tk.Label(r1, text=f"(시스템 최대 {CPU_COUNT}코어)", fg="gray",
                 font=("", 8)).pack(side="left", padx=4)

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

    # ── 코어 수 버튼 ──────────────────────────────
    def _inc_workers(self):
        if self._workers_val < CPU_COUNT:
            self._workers_val += 1
        self._workers_disp.set("최대" if self._workers_val >= CPU_COUNT else str(self._workers_val))

    def _dec_workers(self):
        if self._workers_val > 1:
            self._workers_val -= 1
        self._workers_disp.set(str(self._workers_val))

    def _ok(self):
        save_geometry(self.dlg, "opt_geometry")
        self.result = {
            "scale":              self.scale_var.get(),
            "auto_layer":         self.auto_layer_var.get(),
            "skip_existing":      self.skip_existing_var.get(),
            "include_subfolders": self.include_subfolders_var.get(),
            "dwg_version":        self.dwg_version_var.get(),
            "workers":            self._workers_val,
            "timeout":            self.timeout_var.get(),
            "stop_on_error":      self.stop_on_error_var.get(),
        }
        self.dlg.destroy()

    def _cancel(self):
        save_geometry(self.dlg, "opt_geometry")
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
    dlg     = OptionsDialog(root_hidden)
    options = dlg.show()

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
    folder = filedialog.askdirectory(
        title="SAT 파일이 있는 폴더를 선택하세요",
        parent=root_hidden
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
    log_root.after(100, log_win.poll_queue)

    threading.Thread(
        target=run_conversion,
        args=(accoreconsole_path, sat_files, folder, log_win, options),
        daemon=True,
    ).start()

    log_root.mainloop()


if __name__ == "__main__":
    main()
