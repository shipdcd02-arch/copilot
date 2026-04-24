import os
import queue
import threading
import time
import traceback
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from faster_whisper import WhisperModel

# ── 컬러 ──────────────────────────────────────────────────────────────
C_BG     = "#111827"
C_PANEL  = "#1f2937"
C_CARD   = "#374151"
C_TEXT   = "#f9fafb"
C_DIM    = "#9ca3af"
C_GREEN  = "#34d399"
C_YELLOW = "#fbbf24"
C_BLUE   = "#60a5fa"
C_RED    = "#f87171"
C_ORANGE = "#fb923c"

# ── 유틸 ──────────────────────────────────────────────────────────────
def format_timestamp(seconds: float) -> str:
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def dump_error(label: str):
    try:
        with open("extract_error.txt", "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {label}\n")
            f.write(traceback.format_exc() + "\n")
    except Exception:
        pass

def parse_drop(data: str) -> list[str]:
    import re
    tokens = re.findall(r'\{[^}]+\}|\S+', data)
    return [t[1:-1] if t.startswith('{') and t.endswith('}') else t for t in tokens]


# ── 앱 ────────────────────────────────────────────────────────────────
class ExtractApp:
    VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.wmv')

    def __init__(self, root: TkinterDnD.Tk):
        self.root = root
        self.root.title("자막 추출기")
        self.root.geometry("960x620")
        self.root.configure(bg=C_BG)
        self.root.minsize(700, 450)

        self.files:   list[str]  = []
        self.q        = queue.Queue()
        self.log_q    = queue.Queue()
        self.total    = 0
        self.done     = 0
        self.active   = False
        self.model    = None
        self.lock     = threading.Lock()

        self._build_ui()
        self._poll_logs()

    # ── UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        # 상단바
        bar = tk.Frame(self.root, bg=C_PANEL, pady=10)
        bar.pack(fill=tk.X, padx=10, pady=(10, 5))
        tk.Label(bar, text="자막 추출기", bg=C_PANEL, fg=C_ORANGE,
                 font=("맑은 고딕", 13, "bold")).pack(side=tk.LEFT, padx=14)
        tk.Label(bar, text="Whisper large-v3-turbo  ·  CUDA float16",
                 bg=C_PANEL, fg=C_DIM, font=("Consolas", 8)).pack(side=tk.RIGHT, padx=14)

        body = tk.Frame(self.root, bg=C_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self._build_left(body)
        self._build_right(body)

    def _build_left(self, parent):
        panel = tk.Frame(parent, bg=C_PANEL, width=320)
        panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        panel.pack_propagate(False)

        # 헤더
        hdr = tk.Frame(panel, bg=C_CARD, pady=8)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="파일 목록", bg=C_CARD, fg=C_TEXT,
                 font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT, padx=10)
        self.lbl_count = tk.Label(hdr, text="0개 추가됨", bg=C_CARD, fg=C_DIM,
                                   font=("맑은 고딕", 8))
        self.lbl_count.pack(side=tk.RIGHT, padx=10)

        # 버튼
        btn = tk.Frame(panel, bg=C_PANEL, pady=6)
        btn.pack(fill=tk.X, padx=8)
        for txt, cmd, color in [
            ("파일 선택", self.select_files, C_YELLOW),
            ("폴더 선택", self.select_folder, C_BLUE),
        ]:
            tk.Button(btn, text=txt, command=cmd, bg=color, fg=C_BG,
                      relief=tk.FLAT, font=("맑은 고딕", 10, "bold"),
                      cursor="hand2", pady=6
                      ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        # 드래그 안내
        tk.Label(panel, text="↑ 파일/폴더를 여기에 드래그하세요",
                 bg=C_PANEL, fg=C_DIM, font=("맑은 고딕", 8)
                 ).pack(pady=(0, 4))

        # 리스트
        outer = tk.Frame(panel, bg=C_BG)
        outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        sb = tk.Scrollbar(outer, bg=C_PANEL, troughcolor=C_BG,
                          relief=tk.FLAT, width=10)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_list = tk.Listbox(outer, bg=C_BG, fg=C_TEXT,
                                     selectbackground=C_CARD, activestyle="none",
                                     font=("맑은 고딕", 9), relief=tk.FLAT,
                                     yscrollcommand=sb.set, borderwidth=0)
        self.file_list.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.file_list.yview)

        # 드래그 앤 드롭 등록
        self.file_list.drop_target_register(DND_FILES)
        self.file_list.dnd_bind('<<Drop>>', self._on_drop)

        # 진행바
        prog = tk.Frame(panel, bg=C_PANEL, padx=10, pady=8)
        prog.pack(fill=tk.X)
        row = tk.Frame(prog, bg=C_PANEL)
        row.pack(fill=tk.X, pady=(0, 3))
        tk.Label(row, text="진행", bg=C_PANEL, fg=C_GREEN,
                 font=("맑은 고딕", 9, "bold")).pack(side=tk.LEFT)
        self.lbl_prog = tk.Label(row, text="0 / 0", bg=C_PANEL, fg=C_DIM,
                                  font=("맑은 고딕", 8))
        self.lbl_prog.pack(side=tk.RIGHT)
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("G.Horizontal.TProgressbar", troughcolor=C_CARD,
                    background=C_GREEN, borderwidth=0, thickness=8)
        self.bar = ttk.Progressbar(prog, orient="horizontal",
                                    mode="determinate",
                                    style="G.Horizontal.TProgressbar")
        self.bar.pack(fill=tk.X)

    def _build_right(self, parent):
        panel = tk.Frame(parent, bg=C_PANEL)
        panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        hdr = tk.Frame(panel, bg=C_CARD, pady=7)
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=C_GREEN, width=4).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr, text="음성 추출 로그", bg=C_CARD, fg=C_GREEN,
                 font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT, padx=8)
        self.status = tk.Label(hdr, text="대기중", bg=C_CARD, fg=C_DIM,
                               font=("맑은 고딕", 9))
        self.status.pack(side=tk.RIGHT, padx=10)

        self.log_txt = tk.Text(panel, bg="#0d1117", fg="#c9d1d9",
                               font=("Consolas", 9), relief=tk.FLAT,
                               state=tk.DISABLED, wrap=tk.WORD)
        sb = tk.Scrollbar(panel, command=self.log_txt.yview,
                          bg=C_PANEL, troughcolor=C_BG, relief=tk.FLAT, width=10)
        self.log_txt.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_txt.pack(fill=tk.BOTH, expand=True)
        for tag, fg in [("ok", C_GREEN), ("err", C_RED),
                        ("warn", C_YELLOW), ("info", C_BLUE), ("dim", C_DIM)]:
            self.log_txt.tag_configure(tag, foreground=fg)

    # ── 파일 추가 ─────────────────────────────────────────────────────
    def _on_drop(self, event):
        raw = parse_drop(event.data)
        paths = []
        for p in raw:
            if os.path.isdir(p):
                paths += self._scan_folder(p)
            elif os.path.isfile(p) and p.lower().endswith(self.VIDEO_EXTS):
                paths.append(p)
        if paths:
            self._enqueue(paths)

    def select_files(self):
        paths = filedialog.askopenfilenames(
            title="비디오 파일 선택",
            filetypes=[("Video", "*.mp4 *.mkv *.avi *.mov *.wmv"), ("All", "*.*")]
        )
        if paths:
            self._enqueue(list(paths))

    def select_folder(self):
        folder = filedialog.askdirectory(title="폴더 선택")
        if not folder:
            return
        paths = self._scan_folder(folder)
        if paths:
            self._enqueue(paths)
        else:
            messagebox.showinfo("알림", "비디오 파일이 없습니다.")

    def _scan_folder(self, folder: str) -> list[str]:
        return [
            os.path.join(r, f)
            for r, _, fs in os.walk(folder)
            for f in fs if f.lower().endswith(self.VIDEO_EXTS)
        ]

    def _enqueue(self, paths: list[str]):
        with self.lock:
            for p in paths:
                self.files.append(p)
                self.q.put(p)
                self.file_list.insert(tk.END, f"⏳  {os.path.basename(p)}")
            self.total += len(paths)
            self.lbl_count.config(text=f"{self.total}개 추가됨")
            self._refresh()
            if not self.active:
                self.active = True
                threading.Thread(target=self._worker, daemon=True).start()

    # ── 워커 ─────────────────────────────────────────────────────────
    def _worker(self):
        self.log("Whisper 모델 로딩 중...", "info")
        self.root.after(0, lambda: self.status.config(text="로딩중", fg=C_YELLOW))
        try:
            if self.model is None:
                self.model = WhisperModel(
                    "large-v3-turbo", device="cuda", compute_type="float16"
                )
            self.log("모델 준비 완료 (GPU / float16)", "ok")
            self.root.after(0, lambda: self.status.config(text="실행중", fg=C_GREEN))
        except Exception as e:
            self.log(f"모델 로드 실패: {e}", "err")
            dump_error("Whisper Load")
            self.active = False
            self.root.after(0, lambda: self.status.config(text="오류", fg=C_RED))
            return

        while True:
            try:
                path = self.q.get(timeout=3)
            except queue.Empty:
                break

            name = os.path.basename(path)
            self.log(f"\n▶  {name}", "info")
            self._icon(path, "🔊")

            try:
                segs_iter, info = self.model.transcribe(
                    path, beam_size=5, vad_filter=True
                )
                segments = []
                for s in segs_iter:
                    segments.append(s)
                    if len(segments) % 10 == 0:
                        pct = s.end / max(info.duration, 1) * 100
                        self.log(f"  [{pct:5.1f}%]  {s.text[:40]}", "dim")

                srt_path = os.path.splitext(path)[0] + "_번역전.srt"
                with open(srt_path, "w", encoding="utf-8") as f:
                    for i, s in enumerate(segments, 1):
                        f.write(f"{i}\n")
                        f.write(f"{format_timestamp(s.start)} --> "
                                f"{format_timestamp(s.end)}\n")
                        f.write(f"{s.text.strip()}\n\n")

                self.log(f"  완료: {len(segments)}문장 → "
                         f"{os.path.basename(srt_path)}", "ok")
                self._icon(path, "✅")
                with self.lock:
                    self.done += 1
                self._refresh()

            except Exception:
                self.log(f"  오류 발생", "err")
                dump_error(f"STT: {path}")
                self._icon(path, "❌")

        self.active = False
        self.root.after(0, lambda: self.status.config(text="완료", fg=C_DIM))
        self.log("\n[추출 완료]", "ok")

    # ── 유틸 ─────────────────────────────────────────────────────────
    def _icon(self, path: str, icon: str):
        for i, p in enumerate(self.files):
            if p == path:
                name = os.path.basename(p)
                def _do(idx=i, txt=f"{icon}  {name}"):
                    self.file_list.delete(idx)
                    self.file_list.insert(idx, txt)
                self.root.after(0, _do)
                break

    def _refresh(self):
        def _do():
            t = self.total or 1
            self.lbl_prog.config(text=f"{self.done} / {self.total}")
            self.bar.config(value=self.done / t * 100)
        self.root.after(0, _do)

    def log(self, msg: str, tag: str = ""):
        self.log_q.put((msg, tag))

    def _poll_logs(self):
        try:
            for _ in range(50):
                msg, tag = self.log_q.get_nowait()
                self.log_txt.configure(state=tk.NORMAL)
                self.log_txt.insert(tk.END, msg + "\n", tag or "")
                self.log_txt.see(tk.END)
                self.log_txt.configure(state=tk.DISABLED)
        except queue.Empty:
            pass
        except Exception:
            pass
        self.root.after(80, self._poll_logs)


# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = TkinterDnD.Tk()
    ExtractApp(root)
    root.mainloop()
