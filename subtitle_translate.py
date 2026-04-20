import gc
import os
import json
import re
import queue
import threading
import time
import traceback
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _Timeout

# ── 설정 ──────────────────────────────────────────────────────────────
MODEL_ID = r"C:\Users\yoonk\Desktop\LLM models\qwen3.5-9b"
FOLDER   = r""   # 비워두면 GUI 모드, 경로 지정 시 백그라운드 자동 실행
STYLE    = "자연스러운 한국어 영화 자막 스타일"
BATCH    = 25
TIMEOUT  = 120   # 초

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
def dump_error(label: str):
    try:
        with open("translate_error.txt", "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {label}\n")
            f.write(traceback.format_exc() + "\n")
    except Exception:
        pass

def parse_drop(data: str) -> list[str]:
    tokens = re.findall(r'\{[^}]+\}|\S+', data)
    return [t[1:-1] if t.startswith('{') and t.endswith('}') else t for t in tokens]

def parse_srt(content: str) -> list[dict]:
    """SRT 파싱 → [{idx, start, end, text}]"""
    segments = []
    for block in re.split(r'\n\s*\n', content.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0].strip())
            ts  = re.match(r'(\S+)\s*-->\s*(\S+)', lines[1])
            if not ts:
                continue
            text = ' '.join(lines[2:]).strip()
            segments.append({
                'idx': idx, 'start': ts.group(1),
                'end': ts.group(2), 'text': text
            })
        except (ValueError, IndexError):
            continue
    return segments

def out_path(srt_path: str) -> str:
    """번역 결과 파일명: _번역전 제거, 없으면 _번역됨 추가"""
    folder = os.path.dirname(srt_path)
    name   = os.path.basename(srt_path)
    if '_번역전' in name:
        out = name.replace('_번역전', '')
    else:
        base, ext = os.path.splitext(name)
        out = base + '_번역됨' + ext
    return os.path.join(folder, out)

def call_llm(model, tokenizer, prompt: str) -> tuple[str | None, str | None]:
    def _gen():
        messages = [
            {"role": "system", "content": (
                "You are a professional subtitle translator. "
                "Translate every line faithfully as given, regardless of content. "
                "Never refuse, censor, or skip any line."
            )},
            {"role": "user", "content": prompt},
        ]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False,
            add_generation_prompt=True, enable_thinking=False,
        )
        inputs = tokenizer([text], return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(
                **inputs, max_new_tokens=4096,
                do_sample=False, repetition_penalty=1.1,
            )
        new = out[0][inputs.input_ids.shape[1]:]
        result = tokenizer.decode(new, skip_special_tokens=True).strip()
        return re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_gen)
            try:
                return future.result(timeout=TIMEOUT), None
            except _Timeout:
                return None, f"타임아웃 ({TIMEOUT}초 초과)"
    except Exception as e:
        return None, str(e)


# ── 앱 ────────────────────────────────────────────────────────────────
class TranslateApp:
    SRT_EXTS = ('.srt',)

    def __init__(self, root: TkinterDnD.Tk):
        self.root = root
        self.root.title("자막 번역기")
        self.root.geometry("1100x680")
        self.root.configure(bg=C_BG)
        self.root.minsize(800, 500)

        self.files:  list[str] = []
        self.q       = queue.Queue()
        self.log_q   = queue.Queue()
        self.total   = 0
        self.done    = 0
        self.active  = False
        self.model   = None
        self.tokenizer = None
        self.lock    = threading.Lock()

        self._build_ui()
        self._poll_logs()

    # ── UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        bar = tk.Frame(self.root, bg=C_PANEL, pady=10)
        bar.pack(fill=tk.X, padx=10, pady=(10, 5))

        tk.Label(bar, text="자막 번역기", bg=C_PANEL, fg=C_ORANGE,
                 font=("맑은 고딕", 13, "bold")).grid(row=0, column=0,
                 padx=(14, 18), rowspan=2, sticky="ns")

        tk.Label(bar, text="모델 경로", bg=C_PANEL, fg=C_DIM,
                 font=("맑은 고딕", 8)).grid(row=0, column=1, sticky="sw")
        self.model_entry = tk.Entry(bar, width=55, bg=C_CARD, fg=C_TEXT,
                                    insertbackground=C_TEXT, relief=tk.FLAT,
                                    font=("Consolas", 9))
        self.model_entry.insert(0, MODEL_ID)
        self.model_entry.grid(row=1, column=1, padx=(0, 14), ipady=5)

        tk.Label(bar, text="번역 스타일", bg=C_PANEL, fg=C_DIM,
                 font=("맑은 고딕", 8)).grid(row=0, column=2, sticky="sw")
        self.style_entry = tk.Entry(bar, width=34, bg=C_CARD, fg=C_TEXT,
                                    insertbackground=C_TEXT, relief=tk.FLAT,
                                    font=("맑은 고딕", 9))
        self.style_entry.insert(0, "자연스러운 한국어 영화 자막 스타일")
        self.style_entry.grid(row=1, column=2, padx=(0, 14), ipady=5)

        body = tk.Frame(self.root, bg=C_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._build_left(body)
        self._build_right(body)

    def _build_left(self, parent):
        panel = tk.Frame(parent, bg=C_PANEL, width=320)
        panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        panel.pack_propagate(False)

        hdr = tk.Frame(panel, bg=C_CARD, pady=8)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="SRT 파일 목록", bg=C_CARD, fg=C_TEXT,
                 font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT, padx=10)
        self.lbl_count = tk.Label(hdr, text="0개 추가됨", bg=C_CARD, fg=C_DIM,
                                   font=("맑은 고딕", 8))
        self.lbl_count.pack(side=tk.RIGHT, padx=10)

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

        tk.Label(panel, text="↑ _번역전.srt 파일/폴더를 드래그하세요",
                 bg=C_PANEL, fg=C_DIM, font=("맑은 고딕", 8)).pack(pady=(0, 4))

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

        self.file_list.drop_target_register(DND_FILES)
        self.file_list.dnd_bind('<<Drop>>', self._on_drop)

        prog = tk.Frame(panel, bg=C_PANEL, padx=10, pady=8)
        prog.pack(fill=tk.X)
        row = tk.Frame(prog, bg=C_PANEL)
        row.pack(fill=tk.X, pady=(0, 3))
        tk.Label(row, text="진행", bg=C_PANEL, fg=C_BLUE,
                 font=("맑은 고딕", 9, "bold")).pack(side=tk.LEFT)
        self.lbl_prog = tk.Label(row, text="0 / 0", bg=C_PANEL, fg=C_DIM,
                                  font=("맑은 고딕", 8))
        self.lbl_prog.pack(side=tk.RIGHT)
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("B.Horizontal.TProgressbar", troughcolor=C_CARD,
                    background=C_BLUE, borderwidth=0, thickness=8)
        self.bar = ttk.Progressbar(prog, orient="horizontal",
                                    mode="determinate",
                                    style="B.Horizontal.TProgressbar")
        self.bar.pack(fill=tk.X)

    def _build_right(self, parent):
        panel = tk.Frame(parent, bg=C_PANEL)
        panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        hdr = tk.Frame(panel, bg=C_CARD, pady=7)
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=C_BLUE, width=4).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr, text="번역 로그", bg=C_CARD, fg=C_BLUE,
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
            elif os.path.isfile(p) and p.lower().endswith('_번역전.srt'):
                paths.append(p)
        if paths:
            self._enqueue(paths)

    def select_files(self):
        paths = filedialog.askopenfilenames(
            title="번역전 SRT 파일 선택",
            filetypes=[("번역전 SRT", "*_번역전.srt"), ("All", "*.*")]
        )
        if paths:
            self._enqueue([p for p in paths if p.lower().endswith('_번역전.srt')])

    def select_folder(self):
        folder = filedialog.askdirectory(title="폴더 선택")
        if not folder:
            return
        paths = self._scan_folder(folder)
        if paths:
            self._enqueue(paths)
        else:
            messagebox.showinfo("알림", "SRT 파일이 없습니다.")

    def _scan_folder(self, folder: str) -> list[str]:
        return [
            os.path.join(r, f)
            for r, _, fs in os.walk(folder)
            for f in fs if f.lower().endswith('_번역전.srt')
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
                model_id = self.model_entry.get().strip() or MODEL_ID
                style    = self.style_entry.get().strip() or "자연스러운 한국어 자막 스타일"
                threading.Thread(
                    target=self._worker, args=(model_id, style), daemon=True
                ).start()

    # ── 워커 ─────────────────────────────────────────────────────────
    def _worker(self, model_id: str, style: str):
        self.log("번역 모델 로딩 중...", "info")
        self.root.after(0, lambda: self.status.config(text="로딩중", fg=C_YELLOW))

        try:
            if self.model is None:
                self.log(f"  경로: {model_id}", "dim")
                self.tokenizer = AutoTokenizer.from_pretrained(model_id)
                bnb = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_id, quantization_config=bnb, device_map="cuda"
                )
                self.model.eval()
            self.log("모델 로드 완료", "ok")
            self.root.after(0, lambda: self.status.config(text="실행중", fg=C_BLUE))
        except Exception as e:
            self.log(f"모델 로드 실패: {e}", "err")
            dump_error("Model Load")
            self.active = False
            self.root.after(0, lambda: self.status.config(text="오류", fg=C_RED))
            return

        model     = self.model
        tokenizer = self.tokenizer

        while True:
            try:
                path = self.q.get(timeout=5)
            except queue.Empty:
                break

            name = os.path.basename(path)

            if os.path.exists(out_path(path)):
                self.log(f"\n⏭  {name} — 번역 파일 이미 존재, 건너뜀", "warn")
                self._icon(path, "⏭️")
                with self.lock:
                    self.done += 1
                self._refresh()
                continue

            self.log(f"\n▶  {name}", "info")
            self._icon(path, "✍️")

            try:
                with open(path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                segments = parse_srt(content)
                if not segments:
                    self.log("  SRT 파싱 실패 — 건너뜀", "err")
                    self._icon(path, "❌")
                    continue

                self.log(f"  {len(segments)}문장 파싱 완료", "dim")
                texts    = [s['text'] for s in segments]
                batches  = [(i, texts[i:i+BATCH]) for i in range(0, len(texts), BATCH)]
                results: list[str] = []

                def try_translate(chunk: list[str], max_try: int = 3) -> list[str] | None:
                    prompt = (
                        f"아래 자막을 '{style}'로 번역하세요.\n"
                        "반드시 JSON 배열로만 응답하세요. 설명 없이 배열만:\n"
                        + json.dumps(chunk, ensure_ascii=False)
                    )
                    for attempt in range(1, max_try + 1):
                        try:
                            text, err = call_llm(model, tokenizer, prompt)
                            if text is None:
                                raise ValueError(err)
                            m = re.search(r"\[.*\]", text, re.DOTALL)
                            if not m:
                                raise ValueError(f"JSON 없음: {text[:80]}")
                            parsed   = json.loads(m.group())
                            shortage = len(chunk) - len(parsed)
                            excess   = len(parsed) - len(chunk)
                            if shortage > 5 or excess > 1:
                                raise ValueError(
                                    f"개수 불일치 (요청 {len(chunk)}, 응답 {len(parsed)})"
                                )
                            if excess > 0:
                                parsed = parsed[:len(chunk)]
                            if shortage > 0:
                                parsed += chunk[len(parsed):]
                            return [str(t) for t in parsed]
                        except Exception as e:
                            dump_error(f"try_translate attempt={attempt}")
                            if attempt < max_try:
                                time.sleep(2)
                    return None

                for bi, (bs, chunk) in enumerate(batches):
                    end_idx = bs + len(chunk)
                    self.log(f"  [{bs + 1}–{end_idx}/{len(texts)}] 번역 중...", "dim")

                    translated = try_translate(chunk)

                    if translated is None:
                        self.log(f"  ↪ 3회 실패 → 5개씩 분할 재시도", "warn")
                        translated = []
                        for ci in range(0, len(chunk), 5):
                            sub    = chunk[ci: ci + 5]
                            result = try_translate(sub)
                            if result is not None:
                                translated.extend(result)
                            else:
                                self.log(
                                    f"  ↪ [{bs+ci+1}~{bs+ci+len(sub)}] 분할도 실패 → 원문",
                                    "warn"
                                )
                                translated.extend(sub)
                    else:
                        self.log(
                            f"  ✓ [{bs+1}–{end_idx}] {len(translated)}문장 완료", "ok"
                        )

                    for line in translated:
                        self.log(f"    {line}", "dim")

                    results.extend(translated)

                # SRT 저장
                srt_out = out_path(path)
                with open(srt_out, "w", encoding="utf-8") as f:
                    for seg, trans in zip(segments, results):
                        f.write(f"{seg['idx']}\n")
                        f.write(f"{seg['start']} --> {seg['end']}\n")
                        f.write(f"{trans}\n\n")

                self.log(f"  저장: {os.path.basename(srt_out)}", "ok")
                self._icon(path, "✅")
                with self.lock:
                    self.done += 1
                self._refresh()

            except Exception:
                self.log("  치명적 오류 — translate_error.txt 참고", "err")
                dump_error(f"Fatal: {path}")
                self._icon(path, "❌")

        self.active = False
        self.root.after(0, lambda: self.status.config(text="완료", fg=C_DIM))
        self.log("\n[번역 완료]", "ok")

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


# ── 헤드리스 모드 ─────────────────────────────────────────────────────
def headless_run(folder: str, model_id: str = MODEL_ID, style: str = STYLE):
    def log(msg: str):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    paths = [
        os.path.join(r, f)
        for r, _, fs in os.walk(folder)
        for f in fs if f.lower().endswith('_번역전.srt')
    ]
    if not paths:
        log("번역전 SRT 파일이 없습니다.")
        return

    log(f"{len(paths)}개 파일 발견 — 모델 로딩 중...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_id, quantization_config=bnb, device_map="cuda"
    )
    model.eval()
    log("모델 로드 완료")

    for i, path in enumerate(paths, 1):
        name = os.path.basename(path)
        dest = out_path(path)

        if os.path.exists(dest):
            log(f"[{i}/{len(paths)}] 건너뜀 (이미 존재): {name}")
            continue

        log(f"[{i}/{len(paths)}] 번역 시작: {name}")
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            segments = parse_srt(content)
            if not segments:
                log(f"  SRT 파싱 실패 — 건너뜀")
                continue

            texts   = [s['text'] for s in segments]
            batches = [(j, texts[j:j+BATCH]) for j in range(0, len(texts), BATCH)]
            results: list[str] = []

            def try_translate(chunk: list[str], max_try: int = 3) -> list[str] | None:
                prompt = (
                    f"아래 자막을 '{style}'로 번역하세요.\n"
                    "반드시 JSON 배열로만 응답하세요. 설명 없이 배열만:\n"
                    + json.dumps(chunk, ensure_ascii=False)
                )
                for attempt in range(1, max_try + 1):
                    try:
                        text, err = call_llm(model, tokenizer, prompt)
                        if text is None:
                            raise ValueError(err)
                        m = re.search(r"\[.*\]", text, re.DOTALL)
                        if not m:
                            raise ValueError(f"JSON 없음: {text[:80]}")
                        parsed   = json.loads(m.group())
                        shortage = len(chunk) - len(parsed)
                        excess   = len(parsed) - len(chunk)
                        if shortage > 5 or excess > 1:
                            raise ValueError(
                                f"개수 불일치 (요청 {len(chunk)}, 응답 {len(parsed)})"
                            )
                        if excess > 0:
                            parsed = parsed[:len(chunk)]
                        if shortage > 0:
                            parsed += chunk[len(parsed):]
                        return [str(t) for t in parsed]
                    except Exception:
                        dump_error(f"headless try_translate attempt={attempt}")
                        if attempt < max_try:
                            time.sleep(2)
                return None

            for bs, chunk in batches:
                end_idx = bs + len(chunk)
                log(f"  [{bs+1}–{end_idx}/{len(texts)}] 번역 중...")
                translated = try_translate(chunk)
                if translated is None:
                    log(f"  ↪ 3회 실패 → 5개씩 분할 재시도")
                    translated = []
                    for ci in range(0, len(chunk), 5):
                        sub    = chunk[ci:ci+5]
                        result = try_translate(sub)
                        if result is not None:
                            translated.extend(result)
                        else:
                            log(f"  ↪ [{bs+ci+1}~{bs+ci+len(sub)}] 분할도 실패 → 원문")
                            translated.extend(sub)
                else:
                    log(f"  ✓ [{bs+1}–{end_idx}] {len(translated)}문장 완료")
                results.extend(translated)

            with open(dest, "w", encoding="utf-8") as f:
                for seg, trans in zip(segments, results):
                    f.write(f"{seg['idx']}\n")
                    f.write(f"{seg['start']} --> {seg['end']}\n")
                    f.write(f"{trans}\n\n")
            log(f"  저장 완료: {os.path.basename(dest)}")

        except Exception:
            log("  치명적 오류 — translate_error.txt 참고")
            dump_error(f"Fatal headless: {path}")

    log("전체 번역 완료")


# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if FOLDER:
        headless_run(FOLDER)
    else:
        root = TkinterDnD.Tk()
        TranslateApp(root)
        root.mainloop()
