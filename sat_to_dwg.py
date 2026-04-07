import os
import glob
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import datetime

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

# 스케일 옵션
SCALE_OPTIONS_TOP    = ["AA (1:1)", "BB (1:100)"]
SCALE_OPTIONS_BOTTOM = ["1:1", "1:10", "1:100", "1:1000"]

SCALE_FACTOR_MAP = {
    "AA (1:1)":  1,
    "BB (1:100)": 100,
    "1:1":    1,
    "1:10":   10,
    "1:100":  100,
    "1:1000": 1000,
}

DWG_VERSIONS = ["2018", "2013", "2010", "2007", "2004", "2000", "R14"]

CPU_COUNT       = os.cpu_count() or 2
DEFAULT_WORKERS = max(1, CPU_COUNT - 1)


# ──────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────
def find_accoreconsole():
    for path in ACCORECONSOLE_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def collect_sat_files(folder, include_subfolders):
    """폴더(+하부폴더 옵션)에서 SAT 파일 목록 반환"""
    if include_subfolders:
        result = []
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(".sat"):
                    result.append(os.path.join(root, f))
        return result
    else:
        return glob.glob(os.path.join(folder, "*.sat"))


def sanitize_layer_name(name):
    """AutoCAD 레이어명에 사용 불가한 문자 제거"""
    for ch in r'<>/\"|:;?*=,`':
        name = name.replace(ch, "_")
    return name[:255]  # AutoCAD 레이어명 최대 255자


def build_script(sat_path, dwg_path, options):
    """accoreconsole stdin에 전달할 AutoCAD 스크립트 생성"""
    scale_factor = SCALE_FACTOR_MAP.get(options["scale"], 1)
    use_layer    = options["auto_layer"]
    dwg_version  = options["dwg_version"]
    layer_name   = sanitize_layer_name(
        os.path.splitext(os.path.basename(sat_path))[0]
    )

    lines = []

    # 1) 레이어 생성 및 현재 레이어로 설정
    if use_layer:
        lines += ["-LAYER", "M", layer_name, ""]

    # 2) SAT 가져오기
    lines.append(f'_ACISIN "{sat_path}"')

    # 3) 가져온 객체를 해당 레이어로 이동
    if use_layer:
        lines += ["_CHPROP", "_all", "", "LA", layer_name, ""]

    # 4) 스케일 적용
    if scale_factor != 1:
        lines += ["_SCALE", "_all", "", "0,0,0", str(scale_factor)]

    # 5) 저장 후 종료
    lines += [f'_SAVEAS', dwg_version, f'"{dwg_path}"', "_QUIT Y", ""]

    return "\n".join(lines)


# ──────────────────────────────────────────────
# 단일 파일 변환
# ──────────────────────────────────────────────
def convert_single(accoreconsole_path, sat_path, log_queue, options, stop_event):
    if stop_event.is_set():
        return "cancelled"

    filename = os.path.splitext(os.path.basename(sat_path))[0]
    folder   = os.path.dirname(sat_path)
    dwg_path = os.path.join(folder, filename + ".dwg")

    # 중복 무시
    if options["skip_existing"] and os.path.exists(dwg_path):
        log_queue.put(("skip", f"[건너뜀] {filename}.dwg (이미 존재)"))
        return "skip"

    script = build_script(sat_path, dwg_path, options)

    try:
        result = subprocess.run(
            [
                accoreconsole_path,
                "/nologo",
                "/nohardware",
                "/p", "<<AutoCAD Defaults>>",
            ],
            input=script.encode("cp949", errors="replace"),
            capture_output=True,
            timeout=options.get("timeout", 300),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        stdout = result.stdout.decode("cp949", errors="replace")
        stderr = result.stderr.decode("cp949", errors="replace")

        if os.path.exists(dwg_path):
            log_queue.put(("ok", f"[완료] {filename}.dwg"))
            return "ok"
        else:
            log_queue.put(("err", f"[실패] {filename}.sat — DWG 파일 미생성"))
            output = (stdout + stderr).strip()
            if output:
                log_queue.put(("err", f"       {output[:400]}"))
            return "err"

    except subprocess.TimeoutExpired:
        t = options.get("timeout", 300)
        log_queue.put(("err", f"[시간초과] {filename}.sat ({t}초 초과)"))
        return "err"
    except Exception as e:
        log_queue.put(("err", f"[오류] {filename}.sat — {e}"))
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
        self.done    = 0
        self.ok      = 0
        self.fail    = 0
        self.skip    = 0
        self.log_lines = []
        self.log_queue = queue.Queue()

        root.title("SAT → DWG 변환 중...")
        root.geometry("580x360")
        root.resizable(True, True)
        root.protocol("WM_DELETE_WINDOW", lambda: None)

        self.status_var = tk.StringVar(value=f"변환 중... (0 / {total})")
        tk.Label(root, textvariable=self.status_var, anchor="w",
                 font=("Consolas", 10, "bold")).pack(fill="x", padx=8, pady=(8, 0))

        self.canvas = tk.Canvas(root, height=14, bg="#e0e0e0", highlightthickness=0)
        self.canvas.pack(fill="x", padx=8, pady=4)
        self.bar = self.canvas.create_rectangle(0, 0, 0, 14, fill="#4caf50", width=0)

        self.text = scrolledtext.ScrolledText(
            root, height=14, font=("Consolas", 9),
            state="disabled", bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white"
        )
        self.text.pack(fill="both", expand=True, padx=8, pady=4)
        self.text.tag_config("ok",        foreground="#6adc6a")
        self.text.tag_config("err",       foreground="#f97070")
        self.text.tag_config("skip",      foreground="#c8b400")
        self.text.tag_config("info",      foreground="#9cdcfe")
        self.text.tag_config("cancelled", foreground="#888888")

        btn_row = tk.Frame(root)
        btn_row.pack(pady=(0, 8))
        self.close_btn = tk.Button(
            btn_row, text="닫기", state="disabled", width=10,
            command=self._on_close
        )
        self.close_btn.pack(side="left", padx=4)

    def _on_close(self):
        if self.options.get("log_to_file"):
            self._save_log()
        self.root.destroy()

    def append(self, tag, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        full = f"[{ts}] {msg}"
        self.text.configure(state="normal")
        self.text.insert("end", full + "\n", tag)
        self.text.see("end")
        self.text.configure(state="disabled")
        self.log_lines.append(f"[{tag.upper()}] {full}")

    def update_progress(self):
        self.done += 1
        pct = self.done / self.total if self.total else 1
        self.canvas.update_idletasks()
        w = self.canvas.winfo_width()
        self.canvas.coords(self.bar, 0, 0, int(w * pct), 14)
        self.status_var.set(
            f"변환 중... ({self.done} / {self.total})  "
            f"완료 {self.ok}  실패 {self.fail}  건너뜀 {self.skip}"
        )

    def finish(self):
        self.status_var.set(
            f"완료!  성공 {self.ok}개  /  실패 {self.fail}개  /  "
            f"건너뜀 {self.skip}개  /  전체 {self.total}개"
        )
        self.root.title("SAT → DWG 변환 완료")
        self.close_btn.configure(state="normal")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if self.options.get("log_to_file"):
            self._save_log()
            self.append("info", f"[로그 저장됨] {self.folder}\\sat_to_dwg_log.txt")

    def _save_log(self):
        log_path = os.path.join(self.folder, "sat_to_dwg_log.txt")
        try:
            header = (
                f"SAT → DWG 변환 로그\n"
                f"날짜: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"폴더: {self.folder}\n"
                f"{'─' * 60}\n"
            )
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(header + "\n".join(self.log_lines))
        except Exception:
            pass

    def poll_queue(self):
        try:
            while True:
                tag, msg = self.log_queue.get_nowait()
                self.append(tag, msg)
                if tag == "ok":
                    self.ok += 1
                    self.update_progress()
                elif tag == "err":
                    self.fail += 1
                    self.update_progress()
                elif tag == "skip":
                    self.skip += 1
                    self.update_progress()
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queue)


# ──────────────────────────────────────────────
# 변환 스레드
# ──────────────────────────────────────────────
def run_conversion(accoreconsole_path, sat_files, log_win, options, folder):
    requested_workers = options["workers"]
    actual_workers    = min(requested_workers, len(sat_files))

    log_win.log_queue.put(("info", f"accoreconsole : {accoreconsole_path}"))
    log_win.log_queue.put(("info", f"스케일 : {options['scale']}  /  DWG 버전 : {options['dwg_version']}"))

    if len(sat_files) < requested_workers:
        log_win.log_queue.put((
            "info",
            f"파일 수({len(sat_files)})가 설정 코어 수({requested_workers})보다 적으므로 "
            f"코어를 {actual_workers}개로 조정합니다."
        ))
    log_win.log_queue.put((
        "info",
        f"동시 처리 코어 : {actual_workers}  /  전체 파일 : {len(sat_files)}개\n"
    ))

    stop_event = threading.Event()

    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        futures = {
            executor.submit(
                convert_single, accoreconsole_path, f, log_win.log_queue, options, stop_event
            ): f
            for f in sat_files
        }
        for future in as_completed(futures):
            if stop_event.is_set():
                break
            result = future.result()
            if options.get("stop_on_error") and result == "err":
                stop_event.set()
                log_win.log_queue.put(("err", "[중단] 오류 발생으로 나머지 변환을 중단합니다."))

    log_win.root.after(0, log_win.finish)


# ──────────────────────────────────────────────
# 옵션 설정 창
# ──────────────────────────────────────────────
class OptionsDialog:
    def __init__(self, parent, detected_console):
        self.result = None

        self.dlg = tk.Toplevel(parent)
        self.dlg.title("SAT → DWG 변환 옵션")
        self.dlg.resizable(False, False)
        self.dlg.grab_set()
        self.dlg.geometry("500x620")

        pad = dict(padx=12, pady=5)

        # ── 스케일 ──────────────────────────────
        sf = tk.LabelFrame(self.dlg, text=" 스케일 ", font=("", 9, "bold"), padx=8, pady=6)
        sf.pack(fill="x", **pad)

        self.scale_var = tk.StringVar(value="1:1")

        top_row = tk.Frame(sf)
        top_row.pack(fill="x", pady=(0, 2))
        for label in SCALE_OPTIONS_TOP:
            tk.Radiobutton(
                top_row, text=label, variable=self.scale_var, value=label,
                font=("", 9)
            ).pack(side="left", padx=10)

        ttk.Separator(sf, orient="horizontal").pack(fill="x", pady=4)

        bot_row = tk.Frame(sf)
        bot_row.pack(fill="x")
        for label in SCALE_OPTIONS_BOTTOM:
            tk.Radiobutton(
                bot_row, text=label, variable=self.scale_var, value=label,
                font=("", 9)
            ).pack(side="left", padx=8)

        # ── 변환 옵션 ────────────────────────────
        cf = tk.LabelFrame(self.dlg, text=" 변환 옵션 ", font=("", 9, "bold"), padx=8, pady=6)
        cf.pack(fill="x", **pad)

        self.auto_layer_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            cf, text="레이어 자동변환 (파일명 기준)  — SAT 파일명으로 레이어를 만들고 해당 레이어에 배치",
            variable=self.auto_layer_var, wraplength=420, justify="left"
        ).pack(anchor="w", pady=1)

        self.skip_existing_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            cf, text="중복 무시  — 동일한 이름의 DWG가 이미 존재하면 해당 파일 건너뜀",
            variable=self.skip_existing_var, wraplength=420, justify="left"
        ).pack(anchor="w", pady=1)

        self.include_subfolders_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            cf, text="하부폴더 포함  — 선택 폴더의 모든 하위 폴더에서 SAT를 찾아 각 원본 위치에 DWG 생성",
            variable=self.include_subfolders_var, wraplength=420, justify="left"
        ).pack(anchor="w", pady=1)

        # ── DWG 버전 ────────────────────────────
        vf = tk.LabelFrame(self.dlg, text=" DWG 저장 버전 ", font=("", 9, "bold"), padx=8, pady=6)
        vf.pack(fill="x", **pad)

        ver_row = tk.Frame(vf)
        ver_row.pack(anchor="w")
        self.dwg_version_var = tk.StringVar(value="2018")
        ttk.Combobox(
            ver_row, textvariable=self.dwg_version_var,
            values=DWG_VERSIONS, state="readonly", width=8
        ).pack(side="left")
        tk.Label(ver_row, text="(권장: 2018)", fg="gray", font=("", 8)).pack(side="left", padx=6)

        # ── 고급 옵션 ────────────────────────────
        af = tk.LabelFrame(self.dlg, text=" 고급 옵션 ", font=("", 9, "bold"), padx=8, pady=6)
        af.pack(fill="x", **pad)

        r1 = tk.Frame(af); r1.pack(fill="x", pady=2)
        tk.Label(r1, text="동시 처리 코어 수:").pack(side="left")
        self.workers_var = tk.IntVar(value=DEFAULT_WORKERS)
        tk.Spinbox(r1, from_=1, to=CPU_COUNT, textvariable=self.workers_var, width=4).pack(side="left", padx=4)
        tk.Label(r1, text=f"(시스템 최대 {CPU_COUNT}코어)", fg="gray", font=("", 8)).pack(side="left")

        r2 = tk.Frame(af); r2.pack(fill="x", pady=2)
        tk.Label(r2, text="파일당 제한 시간:").pack(side="left")
        self.timeout_var = tk.IntVar(value=300)
        tk.Spinbox(r2, from_=30, to=3600, increment=30, textvariable=self.timeout_var, width=6).pack(side="left", padx=4)
        tk.Label(r2, text="초", fg="gray", font=("", 8)).pack(side="left")

        self.log_to_file_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            af, text="로그 파일 저장  (선택 폴더에 sat_to_dwg_log.txt 생성)",
            variable=self.log_to_file_var
        ).pack(anchor="w", pady=1)

        self.stop_on_error_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            af, text="오류 발생 시 즉시 중단  (나머지 파일 처리 취소)",
            variable=self.stop_on_error_var
        ).pack(anchor="w", pady=1)

        # ── accoreconsole 경로 ───────────────────
        ef = tk.LabelFrame(self.dlg, text=" accoreconsole.exe 경로 ", font=("", 9, "bold"), padx=8, pady=6)
        ef.pack(fill="x", **pad)

        path_row = tk.Frame(ef); path_row.pack(fill="x")
        self.console_path_var = tk.StringVar(value=detected_console or "")
        tk.Entry(path_row, textvariable=self.console_path_var, width=44).pack(side="left")
        tk.Button(path_row, text="찾아보기", command=self._browse_console).pack(side="left", padx=4)

        if detected_console:
            tk.Label(ef, text="✔ 자동 검색됨", fg="#4caf50", font=("", 8)).pack(anchor="w")
        else:
            tk.Label(ef, text="⚠ 자동 검색 실패 — 경로를 직접 지정해 주세요", fg="#f97070", font=("", 8)).pack(anchor="w")

        # ── 버튼 ────────────────────────────────
        btn_row = tk.Frame(self.dlg)
        btn_row.pack(pady=10)
        tk.Button(btn_row, text="변환 시작", width=14, font=("", 9, "bold"),
                  bg="#4caf50", fg="white", command=self._ok).pack(side="left", padx=6)
        tk.Button(btn_row, text="취소", width=8, command=self._cancel).pack(side="left", padx=6)

        self.dlg.protocol("WM_DELETE_WINDOW", self._cancel)

    def _browse_console(self):
        path = filedialog.askopenfilename(
            title="accoreconsole.exe 선택",
            filetypes=[("실행 파일", "*.exe"), ("모든 파일", "*.*")]
        )
        if path:
            self.console_path_var.set(path)

    def _ok(self):
        console_path = self.console_path_var.get().strip()
        if not console_path or not os.path.exists(console_path):
            messagebox.showerror(
                "경로 오류",
                "accoreconsole.exe 경로가 유효하지 않습니다.\n경로를 확인하거나 직접 지정해 주세요.",
                parent=self.dlg
            )
            return
        self.result = {
            "scale":              self.scale_var.get(),
            "auto_layer":         self.auto_layer_var.get(),
            "skip_existing":      self.skip_existing_var.get(),
            "include_subfolders": self.include_subfolders_var.get(),
            "dwg_version":        self.dwg_version_var.get(),
            "workers":            self.workers_var.get(),
            "timeout":            self.timeout_var.get(),
            "log_to_file":        self.log_to_file_var.get(),
            "stop_on_error":      self.stop_on_error_var.get(),
            "console_path":       console_path,
        }
        self.dlg.destroy()

    def _cancel(self):
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

    # 1) 폴더 선택
    folder = filedialog.askdirectory(title="SAT 파일이 있는 폴더를 선택하세요")
    if not folder:
        root_hidden.destroy()
        return

    # 2) accoreconsole 사전 탐색
    detected_console = find_accoreconsole()

    # 3) 옵션 창 표시
    dlg = OptionsDialog(root_hidden, detected_console)
    options = dlg.show()

    if options is None:
        root_hidden.destroy()
        return

    # 4) SAT 파일 수집
    sat_files = collect_sat_files(folder, options["include_subfolders"])
    if not sat_files:
        scope = "선택한 폴더(및 하위 폴더)" if options["include_subfolders"] else "선택한 폴더"
        messagebox.showwarning("파일 없음", f"{scope}에 SAT 파일이 없습니다.\n{folder}")
        root_hidden.destroy()
        return

    accoreconsole_path = options["console_path"]

    root_hidden.destroy()

    # 5) 로그 창 + 변환 시작
    log_root = tk.Tk()
    log_win  = LogWindow(log_root, total=len(sat_files), options=options, folder=folder)
    log_root.after(100, log_win.poll_queue)

    t = threading.Thread(
        target=run_conversion,
        args=(accoreconsole_path, sat_files, log_win, options, folder),
        daemon=True,
    )
    t.start()

    log_root.mainloop()


if __name__ == "__main__":
    main()
