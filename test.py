import os
import glob
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue

# ──────────────────────────────────────────────
# accoreconsole.exe 경로 후보 (2018 한글판 우선)
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

# CPU 코어 수 자동 감지 (최대 코어 - 1, 최소 1)
MAX_WORKERS = max(1, (os.cpu_count() or 2) - 1)


def find_accoreconsole():
    for path in ACCORECONSOLE_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def convert_single(accoreconsole_path, sat_path, log_queue):
    filename = os.path.splitext(os.path.basename(sat_path))[0]
    folder = os.path.dirname(sat_path)
    dwg_path = os.path.join(folder, filename + ".dwg")

    # stdin으로 직접 전달 (scr 파일 불필요)
    # _SAVEAS: 포맷과 파일명을 별도 줄, 따옴표 없이
    script = (
        f'_ACISIN "{sat_path}"\n'
        f'_SAVEAS\n'
        f'2018\n'
        f'"{dwg_path}"\n'
        f'_QUIT Y\n'
        f'\n'
    )

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
            timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        stdout = result.stdout.decode("cp949", errors="replace")
        stderr = result.stderr.decode("cp949", errors="replace")

        if os.path.exists(dwg_path):
            log_queue.put(("ok", f"[완료] {filename}.dwg"))
            return True
        else:
            log_queue.put(("err", f"[실패] {filename}.sat — DWG 파일 미생성"))
            output = (stdout + stderr).strip()
            if output:
                log_queue.put(("err", f"       {output[:300]}"))
            return False

    except subprocess.TimeoutExpired:
        log_queue.put(("err", f"[시간초과] {filename}.sat (300초 초과)"))
        return False
    except Exception as e:
        log_queue.put(("err", f"[오류] {filename}.sat — {e}"))
        return False


# ──────────────────────────────────────────────
# 로그 창
# ──────────────────────────────────────────────
class LogWindow:
    def __init__(self, root, total):
        self.root = root
        self.total = total
        self.done = 0
        self.ok = 0
        self.fail = 0
        self.log_queue = queue.Queue()

        root.title("SAT → DWG 변환 중...")
        root.geometry("520x320")
        root.resizable(True, True)
        root.protocol("WM_DELETE_WINDOW", lambda: None)  # X 버튼 비활성화

        self.status_var = tk.StringVar(value=f"변환 중... (0 / {total})")
        tk.Label(root, textvariable=self.status_var, anchor="w",
                 font=("Consolas", 10, "bold")).pack(fill="x", padx=8, pady=(8, 0))

        self.canvas = tk.Canvas(root, height=12, bg="#e0e0e0", highlightthickness=0)
        self.canvas.pack(fill="x", padx=8, pady=4)
        self.bar = self.canvas.create_rectangle(0, 0, 0, 12, fill="#4caf50", width=0)

        self.text = scrolledtext.ScrolledText(
            root, height=12, font=("Consolas", 9),
            state="disabled", bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white"
        )
        self.text.pack(fill="both", expand=True, padx=8, pady=4)
        self.text.tag_config("ok",   foreground="#6adc6a")
        self.text.tag_config("err",  foreground="#f97070")
        self.text.tag_config("info", foreground="#9cdcfe")

        self.close_btn = tk.Button(
            root, text="닫기", state="disabled", width=10,
            command=root.destroy
        )
        self.close_btn.pack(pady=(0, 8))

    def append(self, tag, msg):
        self.text.configure(state="normal")
        self.text.insert("end", msg + "\n", tag)
        self.text.see("end")
        self.text.configure(state="disabled")

    def update_progress(self):
        self.done += 1
        pct = self.done / self.total
        self.canvas.update_idletasks()
        w = self.canvas.winfo_width()
        self.canvas.coords(self.bar, 0, 0, int(w * pct), 12)
        self.status_var.set(f"변환 중... ({self.done} / {self.total})")

    def finish(self):
        self.status_var.set(
            f"완료!  성공 {self.ok}개  /  실패 {self.fail}개  /  전체 {self.total}개"
        )
        self.root.title("SAT → DWG 변환 완료")
        self.close_btn.configure(state="normal")
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def poll_queue(self):
        try:
            while True:
                tag, msg = self.log_queue.get_nowait()
                self.append(tag, msg)
                if tag == "ok":
                    self.ok += 1
                elif tag == "err":
                    self.fail += 1
                if tag in ("ok", "err"):
                    self.update_progress()
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queue)


# ──────────────────────────────────────────────
# 변환 스레드
# ──────────────────────────────────────────────
def run_conversion(accoreconsole_path, sat_files, log_win):
    log_win.log_queue.put(("info", f"accoreconsole : {accoreconsole_path}"))
    log_win.log_queue.put(("info", f"동시 처리 코어 : {MAX_WORKERS}  /  전체 파일 : {len(sat_files)}개\n"))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(convert_single, accoreconsole_path, f, log_win.log_queue): f
            for f in sat_files
        }
        for _ in as_completed(futures):
            pass

    log_win.root.after(0, log_win.finish)


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
def main():
    root_hidden = tk.Tk()
    root_hidden.withdraw()

    folder = filedialog.askdirectory(title="SAT 파일이 있는 폴더를 선택하세요")
    root_hidden.destroy()

    if not folder:
        return

    sat_files = glob.glob(os.path.join(folder, "*.sat"))
    if not sat_files:
        messagebox.showwarning("파일 없음", f"선택한 폴더에 SAT 파일이 없습니다.\n{folder}")
        return

    accoreconsole_path = find_accoreconsole()
    if not accoreconsole_path:
        messagebox.showerror(
            "accoreconsole 없음",
            "accoreconsole.exe를 찾을 수 없습니다.\n"
            "sat_to_dwg.py 상단의 ACCORECONSOLE_CANDIDATES 목록에\n"
            "설치된 경로를 직접 추가해 주세요."
        )
        return

    log_root = tk.Tk()
    log_win = LogWindow(log_root, total=len(sat_files))
    log_root.after(100, log_win.poll_queue)

    t = threading.Thread(
        target=run_conversion,
        args=(accoreconsole_path, sat_files, log_win),
        daemon=True,
    )
    t.start()

    log_root.mainloop()


if __name__ == "__main__":
    main()
