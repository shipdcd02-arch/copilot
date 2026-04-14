import os
import json
import threading
import queue
import time
import re
import traceback
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from faster_whisper import WhisperModel
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from deep_translator import GoogleTranslator

# ──────────────────────────────────────────────────────────────────────
# 기본 설정
# ──────────────────────────────────────────────────────────────────────
DEFAULT_API_KEY = ""          # 여기에 API 키 입력 (또는 UI에서 입력)
MODEL_NAME = "gemini-2.5-flash"

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT:       HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH:      HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# ──────────────────────────────────────────────────────────────────────
# 컬러 팔레트
# ──────────────────────────────────────────────────────────────────────
C_BG       = "#111827"   # 배경
C_PANEL    = "#1f2937"   # 패널
C_CARD     = "#374151"   # 카드/헤더
C_BORDER   = "#4b5563"
C_TEXT     = "#f9fafb"
C_DIM      = "#9ca3af"
C_GREEN    = "#34d399"
C_BLUE     = "#60a5fa"
C_YELLOW   = "#fbbf24"
C_RED      = "#f87171"
C_ORANGE   = "#fb923c"

# ──────────────────────────────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────────────────────────────
def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def dump_error(label: str):
    try:
        with open("error_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {label}\n")
            f.write(traceback.format_exc() + "\n")
    except Exception:
        pass

def safe_response_text(resp) -> tuple[str | None, str | None]:
    """
    Gemini 응답에서 안전하게 텍스트를 추출합니다.
    반환: (text, error_message)
    크래시 원인 #1 해결: resp.text 직접 접근 대신 단계적으로 확인
    """
    # 1) 프롬프트 차단 여부 확인
    try:
        fb = resp.prompt_feedback
        if fb and getattr(fb, "block_reason", None):
            return None, f"프롬프트 차단됨: {fb.block_reason}"
    except Exception:
        pass

    # 2) candidates 확인
    try:
        if not resp.candidates:
            return None, "candidates 없음 (빈 응답)"
        candidate = resp.candidates[0]
        finish = getattr(candidate, "finish_reason", None)
        # finish_reason 2 = SAFETY, 3 = RECITATION 등
        if finish and str(finish) not in ("FinishReason.STOP", "1", "STOP"):
            pass  # 일단 텍스트 추출 시도
        if candidate.content and candidate.content.parts:
            return candidate.content.parts[0].text, None
    except Exception as e:
        pass

    # 3) 최후 수단: .text 직접 접근
    try:
        return resp.text, None
    except Exception as e:
        return None, f"텍스트 추출 불가: {e}"


# ──────────────────────────────────────────────────────────────────────
# 앱
# ──────────────────────────────────────────────────────────────────────
class SubtitleApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AI 자막 생성기")
        self.root.geometry("1400x860")
        self.root.configure(bg=C_BG)
        self.root.minsize(1000, 650)

        # 상태
        self.files: list[dict] = []          # {path, name, status}
        self.stt_queue:   queue.Queue = queue.Queue()
        self.trans_queue: queue.Queue = queue.Queue()
        self.log_queue:   queue.Queue = queue.Queue()
        self.total = 0
        self.stt_done = 0
        self.trans_done = 0
        self.active_stt   = False
        self.active_trans = False
        self.lock = threading.Lock()

        self._build_ui()
        self._poll_logs()

    # ── UI 구성 ──────────────────────────────────────────────────────

    def _build_ui(self):
        self._setup_styles()
        self._build_topbar()

        body = tk.Frame(self.root, bg=C_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self._build_left_panel(body)
        self._build_right_panel(body)

    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Green.Horizontal.TProgressbar",
                    troughcolor=C_CARD, background=C_GREEN,
                    borderwidth=0, thickness=8)
        s.configure("Blue.Horizontal.TProgressbar",
                    troughcolor=C_CARD, background=C_BLUE,
                    borderwidth=0, thickness=8)

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=C_PANEL, pady=10)
        bar.pack(fill=tk.X, padx=10, pady=(10, 5))

        # 제목
        tk.Label(bar, text="AI 자막 생성기", bg=C_PANEL, fg=C_ORANGE,
                 font=("맑은 고딕", 13, "bold")).grid(row=0, column=0, padx=(14, 18), rowspan=2, sticky="ns")

        # API 키
        tk.Label(bar, text="Gemini API 키", bg=C_PANEL, fg=C_DIM,
                 font=("맑은 고딕", 8)).grid(row=0, column=1, sticky="sw", padx=(0, 2))
        self.key_entry = tk.Entry(bar, width=52, bg=C_CARD, fg=C_TEXT,
                                  insertbackground=C_TEXT, relief=tk.FLAT,
                                  font=("Consolas", 9))
        self.key_entry.insert(0, DEFAULT_API_KEY)
        self.key_entry.grid(row=1, column=1, padx=(0, 14), ipady=5)

        # 번역 스타일
        tk.Label(bar, text="번역 스타일", bg=C_PANEL, fg=C_DIM,
                 font=("맑은 고딕", 8)).grid(row=0, column=2, sticky="sw", padx=(0, 2))
        self.style_entry = tk.Entry(bar, width=34, bg=C_CARD, fg=C_TEXT,
                                    insertbackground=C_TEXT, relief=tk.FLAT,
                                    font=("맑은 고딕", 9))
        self.style_entry.insert(0, "자연스러운 한국어 영화 자막 스타일")
        self.style_entry.grid(row=1, column=2, padx=(0, 14), ipady=5)

        # 오류 전략
        tk.Label(bar, text="오류 시 전략", bg=C_PANEL, fg=C_DIM,
                 font=("맑은 고딕", 8)).grid(row=0, column=3, sticky="sw", padx=(0, 2))
        strat_frame = tk.Frame(bar, bg=C_PANEL)
        strat_frame.grid(row=1, column=3, sticky="w")
        self.error_strategy = tk.StringVar(value="Retry")
        for label, val in [("재시도 (20초)", "Retry"), ("구글 우회", "Bypass")]:
            tk.Radiobutton(strat_frame, text=label, variable=self.error_strategy,
                           value=val, bg=C_PANEL, fg=C_DIM, selectcolor=C_CARD,
                           activebackground=C_PANEL, font=("맑은 고딕", 9)
                           ).pack(side=tk.LEFT, padx=4)

        # 모델명 표시
        tk.Label(bar, text=f"모델: {MODEL_NAME}", bg=C_PANEL, fg=C_DIM,
                 font=("Consolas", 8)).grid(row=0, column=4, sticky="se", padx=14)

    def _build_left_panel(self, parent):
        panel = tk.Frame(parent, bg=C_PANEL, width=360)
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
        btn_row = tk.Frame(panel, bg=C_PANEL, pady=8)
        btn_row.pack(fill=tk.X, padx=8)
        for txt, cmd, color in [
            ("파일 선택", self.select_files, C_YELLOW),
            ("폴더 선택", self.select_folder, C_BLUE),
        ]:
            tk.Button(btn_row, text=txt, command=cmd,
                      bg=color, fg=C_BG, relief=tk.FLAT,
                      font=("맑은 고딕", 10, "bold"),
                      cursor="hand2", pady=7
                      ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        # 파일 리스트
        list_outer = tk.Frame(panel, bg=C_BG, relief=tk.FLAT)
        list_outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        sb = tk.Scrollbar(list_outer, bg=C_PANEL, troughcolor=C_BG,
                          relief=tk.FLAT, width=10)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_list = tk.Listbox(list_outer, bg=C_BG, fg=C_TEXT,
                                     selectbackground=C_CARD, activestyle="none",
                                     font=("맑은 고딕", 9), relief=tk.FLAT,
                                     yscrollcommand=sb.set, borderwidth=0)
        self.file_list.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.file_list.yview)

        # 진행 바
        prog_frame = tk.Frame(panel, bg=C_PANEL, padx=10, pady=8)
        prog_frame.pack(fill=tk.X)

        for label, color, style_name, attr_lbl, attr_bar in [
            ("음성 추출", C_GREEN, "Green.Horizontal.TProgressbar", "lbl_stt", "bar_stt"),
            ("AI 번역",  C_BLUE,  "Blue.Horizontal.TProgressbar",  "lbl_trans", "bar_trans"),
        ]:
            row = tk.Frame(prog_frame, bg=C_PANEL)
            row.pack(fill=tk.X, pady=(4, 1))
            tk.Label(row, text=label, bg=C_PANEL, fg=color,
                     font=("맑은 고딕", 9, "bold"), width=8, anchor="w").pack(side=tk.LEFT)
            lbl = tk.Label(row, text="0 / 0", bg=C_PANEL, fg=C_DIM,
                           font=("맑은 고딕", 8))
            lbl.pack(side=tk.RIGHT)
            setattr(self, attr_lbl, lbl)

            bar = ttk.Progressbar(prog_frame, orient="horizontal",
                                  mode="determinate", style=style_name)
            bar.pack(fill=tk.X, pady=(0, 6))
            setattr(self, attr_bar, bar)

    def _build_right_panel(self, parent):
        panel = tk.Frame(parent, bg=C_BG)
        panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for title, color, attr, status_attr in [
            ("음성 추출 로그 (Whisper)",  C_GREEN, "log_stt",   "status_stt"),
            ("AI 번역 로그 (Gemini)",     C_BLUE,  "log_trans", "status_trans"),
        ]:
            frame = tk.Frame(panel, bg=C_PANEL)
            frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

            hdr = tk.Frame(frame, bg=C_CARD, pady=7)
            hdr.pack(fill=tk.X)
            tk.Frame(hdr, bg=color, width=4).pack(side=tk.LEFT, fill=tk.Y)
            tk.Label(hdr, text=title, bg=C_CARD, fg=color,
                     font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT, padx=8)
            status = tk.Label(hdr, text="대기중", bg=C_CARD, fg=C_DIM,
                              font=("맑은 고딕", 9))
            status.pack(side=tk.RIGHT, padx=10)
            setattr(self, status_attr, status)

            txt = tk.Text(frame, bg="#0d1117", fg="#c9d1d9",
                          font=("Consolas", 9), relief=tk.FLAT,
                          state=tk.DISABLED, wrap=tk.WORD)
            sb = tk.Scrollbar(frame, command=txt.yview,
                              bg=C_PANEL, troughcolor=C_BG, relief=tk.FLAT, width=10)
            txt.configure(yscrollcommand=sb.set)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            txt.pack(fill=tk.BOTH, expand=True)
            setattr(self, attr, txt)

            # 태그 색상
            for tag, fg in [
                ("ok",   C_GREEN), ("err", C_RED),
                ("warn", C_YELLOW), ("info", C_BLUE), ("dim", C_DIM),
            ]:
                txt.tag_configure(tag, foreground=fg)

    # ── 파일 선택 ────────────────────────────────────────────────────

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
        exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv')
        paths = [
            os.path.join(r, f)
            for r, _, fs in os.walk(folder)
            for f in fs if f.lower().endswith(exts)
        ]
        if paths:
            self._enqueue(paths)
        else:
            messagebox.showinfo("알림", "선택한 폴더에 비디오 파일이 없습니다.")

    def _enqueue(self, paths: list[str]):
        with self.lock:
            for p in paths:
                self.files.append({"path": p, "status": "대기중"})
                self.stt_queue.put(p)
                name = self._short(p)
                self.file_list.insert(tk.END, f"⏳  {name}")
            self.total += len(paths)
            self.lbl_count.config(text=f"{self.total}개 추가됨")
            self._refresh_progress()

            if not self.active_stt:
                self.active_stt = True
                threading.Thread(target=self._stt_worker, daemon=True).start()
            if not self.active_trans:
                self.active_trans = True
                # API 키를 메인 스레드에서 미리 읽어서 넘김 (tkinter 스레드 안전)
                api_key = self.key_entry.get().strip()
                threading.Thread(target=self._trans_worker, args=(api_key,), daemon=True).start()

    # ── 유틸 ─────────────────────────────────────────────────────────

    def _short(self, path: str, maxlen: int = 42) -> str:
        name = os.path.basename(path)
        return name if len(name) <= maxlen else name[:maxlen - 3] + "..."

    def _set_file_icon(self, path: str, icon: str):
        for i, f in enumerate(self.files):
            if f["path"] == path:
                name = self._short(path)
                def _do(idx=i, txt=f"{icon}  {name}"):
                    self.file_list.delete(idx)
                    self.file_list.insert(idx, txt)
                self.root.after(0, _do)
                break

    def _refresh_progress(self):
        def _do():
            t = self.total or 1
            s_pct = self.stt_done / t * 100
            tr_pct = self.trans_done / t * 100
            self.lbl_stt.config(text=f"{self.stt_done} / {self.total}")
            self.bar_stt.config(value=s_pct)
            self.lbl_trans.config(text=f"{self.trans_done} / {self.total}")
            self.bar_trans.config(value=tr_pct)
        self.root.after(0, _do)

    def log(self, channel: str, msg: str, tag: str = ""):
        self.log_queue.put((channel, msg, tag))

    def _poll_logs(self):
        try:
            for _ in range(50):            # 한 번에 최대 50줄 처리
                channel, msg, tag = self.log_queue.get_nowait()
                widget = self.log_stt if channel == "STT" else self.log_trans
                widget.configure(state=tk.NORMAL)
                widget.insert(tk.END, msg + "\n", tag or "")
                widget.see(tk.END)
                widget.configure(state=tk.DISABLED)
        except queue.Empty:
            pass
        except Exception:
            pass
        self.root.after(80, self._poll_logs)

    # ── STT 워커 ─────────────────────────────────────────────────────

    def _stt_worker(self):
        self.log("STT", "Whisper 모델 로딩 중...", "info")
        self.root.after(0, lambda: self.status_stt.config(text="로딩중", fg=C_YELLOW))

        try:
            model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
            self.log("STT", "모델 준비 완료 (GPU / float16)", "ok")
            self.root.after(0, lambda: self.status_stt.config(text="실행중", fg=C_GREEN))
        except Exception as e:
            self.log("STT", f"모델 로드 실패: {e}", "err")
            dump_error("STT Model Load")
            self.active_stt = False
            self.root.after(0, lambda: self.status_stt.config(text="오류", fg=C_RED))
            return

        while True:
            try:
                path = self.stt_queue.get(timeout=3)
            except queue.Empty:
                break

            name = os.path.basename(path)
            self.log("STT", f"\n▶  {name}", "info")
            self._set_file_icon(path, "🔊")

            try:
                segs_iter, info = model.transcribe(path, beam_size=5, vad_filter=True)
                segments = []
                for s in segs_iter:
                    segments.append({"start": s.start, "end": s.end, "text": s.text})
                    pct = s.end / max(info.duration, 1) * 100
                    if len(segments) % 5 == 0:
                        self.log("STT", f"  [{pct:5.1f}%]  {s.text[:35]}", "dim")

                self.log("STT", f"  완료: {len(segments)}문장 추출됨", "ok")
                self.trans_queue.put({"path": path, "segs": segments})

                with self.lock:
                    self.stt_done += 1
                self._refresh_progress()

            except Exception:
                self.log("STT", f"  오류 발생 — error_log.txt 참고", "err")
                dump_error(f"STT: {path}")
                self._set_file_icon(path, "❌")

        self.active_stt = False
        self.root.after(0, lambda: self.status_stt.config(text="완료", fg=C_DIM))
        self.log("STT", "\n[음성 추출 완료]", "ok")

    # ── 번역 워커 ────────────────────────────────────────────────────

    def _trans_worker(self, api_key: str):
        self.log("TRANS", "번역 워커 시작", "info")
        self.root.after(0, lambda: self.status_trans.config(text="초기화중", fg=C_YELLOW))

        if not api_key:
            self.log("TRANS", "API 키가 비어 있습니다. 상단에서 입력하세요.", "err")
            self.active_trans = False
            return

        try:
            genai.configure(api_key=api_key)
            gem = genai.GenerativeModel(MODEL_NAME)
            self.log("TRANS", f"Gemini 준비 완료 ({MODEL_NAME})", "ok")
        except Exception:
            self.log("TRANS", "Gemini 초기화 실패 — error_log.txt 참고", "err")
            dump_error("Gemini Init")
            self.active_trans = False
            self.root.after(0, lambda: self.status_trans.config(text="오류", fg=C_RED))
            return

        google_trans = GoogleTranslator(source="auto", target="ko")
        self.root.after(0, lambda: self.status_trans.config(text="실행중", fg=C_BLUE))

        while True:
            try:
                task = self.trans_queue.get(timeout=5)
            except queue.Empty:
                if not self.active_stt and self.stt_queue.empty():
                    break
                continue

            path  = task["path"]
            segs  = task["segs"]
            name  = os.path.basename(path)
            srt   = os.path.splitext(path)[0] + ".srt"
            style = self.style_entry.get().strip() or "자연스러운 한국어 자막 스타일"

            self.log("TRANS", f"\n▶  {name}  ({len(segs)}문장)", "info")
            self._set_file_icon(path, "✍️")

            try:
                srt_lines = []
                BATCH = 100

                for batch_start in range(0, len(segs), BATCH):
                    batch  = segs[batch_start: batch_start + BATCH]
                    texts  = [s["text"].strip() for s in batch]
                    prompt = (
                        f"아래 자막을 '{style}'로 번역하세요.\n"
                        "반드시 JSON 배열로만 응답하세요. 설명 없이 배열만:\n"
                        + json.dumps(texts, ensure_ascii=False)
                    )

                    translated: list[str] = []
                    attempt = 0

                    while not translated:
                        attempt += 1
                        end_idx = min(batch_start + BATCH, len(segs))
                        self.log("TRANS",
                                 f"  [{batch_start + 1}–{end_idx}/{len(segs)}] "
                                 f"API 요청 중... (시도 {attempt})", "dim")
                        try:
                            # ── 핵심 수정: resp.text 직접 접근 금지 ──
                            resp = gem.generate_content(prompt,
                                                        safety_settings=SAFETY_SETTINGS)
                            text, err = safe_response_text(resp)

                            if text is None:
                                raise ValueError(f"응답 텍스트 없음: {err}")

                            m = re.search(r"\[.*\]", text, re.DOTALL)
                            if not m:
                                raise ValueError(f"JSON 배열 없음. 응답 앞부분: {text[:120]}")

                            parsed = json.loads(m.group())
                            if len(parsed) != len(texts):
                                raise ValueError(
                                    f"개수 불일치 (요청 {len(texts)}, 응답 {len(parsed)})"
                                )

                            translated = [str(t) for t in parsed]
                            self.log("TRANS", f"  ✓ {len(translated)}문장 번역 완료", "ok")

                        except Exception as api_err:
                            err_msg = str(api_err)
                            self.log("TRANS", f"  ✗ API 오류: {err_msg[:90]}", "err")
                            dump_error(f"API attempt={attempt} path={path}")

                            if self.error_strategy.get() == "Bypass":
                                self.log("TRANS", "  ↪ 구글 번역으로 우회...", "warn")
                                try:
                                    translated = [google_trans.translate(t) or t for t in texts]
                                except Exception as ge:
                                    self.log("TRANS", f"  구글 번역도 실패: {ge}", "err")
                                    translated = texts  # 원문 그대로
                            else:
                                wait = min(20 * attempt, 120)
                                self.log("TRANS", f"  ↪ {wait}초 대기 후 재시도...", "warn")
                                time.sleep(wait)

                    # SRT 블록 생성
                    for j, seg in enumerate(batch):
                        idx  = batch_start + j + 1
                        line = translated[j] if j < len(translated) else seg["text"]
                        srt_lines.append(
                            f"{idx}\n"
                            f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}\n"
                            f"{line}\n"
                        )
                        if idx % 20 == 0:
                            self.log("TRANS", f"  [{idx}]  {line[:40]}", "dim")

                    time.sleep(0.1)   # API 레이트 리밋 여유

                # SRT 파일 저장
                with open(srt, "w", encoding="utf-8") as f:
                    f.write("\n".join(srt_lines))

                self.log("TRANS", f"  저장: {os.path.basename(srt)}", "ok")
                self._set_file_icon(path, "✅")

                with self.lock:
                    self.trans_done += 1
                self._refresh_progress()

            except Exception:
                self.log("TRANS", f"  치명적 오류 발생 — error_log.txt 참고", "err")
                dump_error(f"Trans fatal: {path}")
                self._set_file_icon(path, "❌")

        self.active_trans = False
        self.root.after(0, lambda: self.status_trans.config(text="완료", fg=C_DIM))
        self.log("TRANS", "\n[AI 번역 완료]", "ok")


# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        root = tk.Tk()
        SubtitleApp(root)
        root.mainloop()
    except Exception:
        dump_error("Main Loop Crash")
