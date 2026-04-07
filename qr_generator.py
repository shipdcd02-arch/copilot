import tkinter as tk
from tkinter import messagebox
import time
import qrcode
from PIL import Image, ImageTk

MAX_BYTES = 2000

# ── 색상 팔레트 ──────────────────────────────────────────
BG          = "#F0F4F8"
CARD        = "#FFFFFF"
BORDER      = "#D1DCE8"
TEXT        = "#2D3748"
TEXT_MUTED  = "#8A9BB0"
PRIMARY     = "#4F86F0"
PRIMARY_HOV = "#3A6FD4"
DANGER      = "#E05C5C"
DANGER_HOV  = "#C44A4A"
CTRL        = "#5BA67A"
CTRL_HOV    = "#469060"
NEUTRAL     = "#7A8FA6"
NEUTRAL_HOV = "#5F7A92"
PROGRESS_BG = "#D1DCE8"
PROGRESS_FG = "#5BA67A"
FONT        = "맑은 고딕"

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS


def split_text_by_newlines(text, max_bytes=MAX_BYTES):
    lines = text.split('\n')
    chunks, current_lines, current_bytes = [], [], 0
    for line in lines:
        lb = len((line + '\n').encode('utf-8'))
        if current_lines and current_bytes + lb > max_bytes:
            chunks.append('\n'.join(current_lines))
            current_lines, current_bytes = [line], lb
        else:
            current_lines.append(line)
            current_bytes += lb
    if current_lines:
        chunks.append('\n'.join(current_lines))
    return chunks


def styled_btn(parent, text, command, bg, hover, width=9, state=tk.NORMAL):
    btn = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=CARD, activebackground=hover, activeforeground=CARD,
        relief=tk.FLAT, bd=0, cursor="hand2",
        font=(FONT, 10, "bold"), width=width,
        padx=6, pady=6, state=state,
        disabledforeground="#AAAAAA"
    )
    def on_enter(e):
        if btn["state"] != tk.DISABLED:
            btn.config(bg=hover)
    def on_leave(e):
        if btn["state"] != tk.DISABLED:
            btn.config(bg=bg)
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    btn._base_bg = bg
    btn._hover_bg = hover
    return btn


def restore_btn_color(btn):
    btn.config(bg=btn._base_bg)


# ════════════════════════════════════════════════════════
#  QR 재생 창 (별도 Toplevel)
# ════════════════════════════════════════════════════════

class QRPlayerWindow:
    def __init__(self, parent, qr_images, speed_var):
        self.parent = parent
        self.qr_images = qr_images
        self.speed_var = speed_var          # 메인 창의 speed_var 공유
        self.current_qr_index = 0
        self.animation_job = None
        self.is_playing = False
        self.progress_start_time = 0.0

        self.win = tk.Toplevel(parent)
        self.win.title("QR 재생")
        self.win.resizable(False, False)
        self.win.configure(bg=BG)
        self.win.transient(parent)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        outer = tk.Frame(self.win, bg=BG, padx=20, pady=18)
        outer.pack()

        # ── 타이틀 행 ────────────────────────────────────
        title_row = tk.Frame(outer, bg=BG)
        title_row.pack(fill=tk.X, pady=(0, 14))
        tk.Label(title_row, text="QR 재생",
                 bg=BG, fg=TEXT, font=(FONT, 13, "bold")).pack(side=tk.LEFT)
        self.total_label = tk.Label(
            title_row,
            text=f"총 {len(qr_images)}장",
            bg=BG, fg=TEXT_MUTED, font=(FONT, 10)
        )
        self.total_label.pack(side=tk.RIGHT, padx=(0, 2))

        # ── QR 표시 카드 ─────────────────────────────────
        qr_card = tk.Frame(outer, bg=CARD,
                           highlightbackground=BORDER, highlightthickness=1)
        qr_card.pack(pady=(0, 10))

        self.qr_label = tk.Label(qr_card, bg=CARD, width=360, height=360)
        self.qr_label.pack(padx=16, pady=(14, 6))

        self.page_label = tk.Label(qr_card, text="",
                                   bg=CARD, fg=TEXT_MUTED, font=(FONT, 11))
        self.page_label.pack(pady=(0, 8))

        # 프로그레스 바
        progress_frame = tk.Frame(qr_card, bg=CARD, padx=16)
        progress_frame.pack(fill=tk.X, pady=(0, 14))
        self.progress_canvas = tk.Canvas(
            progress_frame, height=8, bg=PROGRESS_BG,
            highlightthickness=0, bd=0
        )
        self.progress_canvas.pack(fill=tk.X)
        self.progress_fill = self.progress_canvas.create_rectangle(
            0, 0, 0, 8, fill=PROGRESS_FG, outline=""
        )

        # ── 재생 제어 카드 ───────────────────────────────
        ctrl_card = tk.Frame(outer, bg=CARD,
                             highlightbackground=BORDER, highlightthickness=1)
        ctrl_card.pack(fill=tk.X, pady=(0, 4))
        inner_ctrl = tk.Frame(ctrl_card, bg=CARD, padx=12, pady=10)
        inner_ctrl.pack(fill=tk.X)

        ctrl_btn_row = tk.Frame(inner_ctrl, bg=CARD)
        ctrl_btn_row.pack(fill=tk.X)

        has_multi = len(qr_images) > 1
        self.btn_start = styled_btn(ctrl_btn_row, "▶  시작", self.start_animation,
                                    CTRL, CTRL_HOV, width=10,
                                    state=tk.NORMAL if has_multi else tk.DISABLED)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_pause = styled_btn(ctrl_btn_row, "⏸  일시정지", self.pause_animation,
                                    NEUTRAL, NEUTRAL_HOV, width=10, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_reset = styled_btn(ctrl_btn_row, "↩  처음으로", self.reset_animation,
                                    NEUTRAL, NEUTRAL_HOV, width=10,
                                    state=tk.NORMAL if has_multi else tk.DISABLED)
        self.btn_reset.pack(side=tk.LEFT)

        # 속도 조절
        speed_row = tk.Frame(inner_ctrl, bg=CARD)
        speed_row.pack(fill=tk.X, pady=(10, 0))
        tk.Label(speed_row, text="전환 간격",
                 bg=CARD, fg=TEXT_MUTED, font=(FONT, 9)).pack(side=tk.LEFT)
        self.speed_entry = tk.Spinbox(
            speed_row, from_=0.1, to=10.0, increment=0.1,
            textvariable=self.speed_var, width=5,
            format="%.1f", font=(FONT, 10),
            bg=CARD, fg=TEXT, relief=tk.FLAT,
            highlightbackground=BORDER, highlightthickness=1,
            buttonbackground=BG
        )
        self.speed_entry.pack(side=tk.LEFT, padx=6)
        tk.Label(speed_row, text="초", bg=CARD, fg=TEXT_MUTED, font=(FONT, 9)).pack(side=tk.LEFT)

        # 첫 QR 표시
        self._show_current()

    # ── 유틸 ──────────────────────────────────────────────

    def get_interval_ms(self):
        try:
            val = float(self.speed_var.get())
            return max(100, int(val * 1000))
        except ValueError:
            return 500

    def _draw_progress(self, fraction):
        self.progress_canvas.update_idletasks()
        w = self.progress_canvas.winfo_width()
        if w <= 1:
            w = 360
        bar_w = int(w * max(0.0, min(fraction, 1.0)))
        self.progress_canvas.coords(self.progress_fill, 0, 0, bar_w, 8)

    def _set_ctrl_state(self, start, pause, reset):
        def apply(btn, enabled):
            btn.config(state=tk.NORMAL if enabled else tk.DISABLED)
            if enabled:
                restore_btn_color(btn)
        apply(self.btn_start, start)
        apply(self.btn_pause, pause)
        apply(self.btn_reset, reset)

    def _show_current(self):
        if not self.qr_images:
            return
        self.qr_label.config(image=self.qr_images[self.current_qr_index])
        self.page_label.config(
            text=f"{self.current_qr_index + 1}  /  {len(self.qr_images)}"
        )

    def _stop_animation(self):
        if self.animation_job:
            self.win.after_cancel(self.animation_job)
            self.animation_job = None
        self.is_playing = False

    def _on_close(self):
        self._stop_animation()
        self.win.destroy()

    # ── 재생 제어 ─────────────────────────────────────────

    def start_animation(self):
        if self.is_playing:
            return
        # 재생 완료 후 시작 → 처음부터 다시
        self.current_qr_index = 0
        self._show_current()
        self._draw_progress(0)
        self.is_playing = True
        self._set_ctrl_state(start=False, pause=True, reset=True)
        self._start_progress()

    def pause_animation(self):
        self._stop_animation()
        self._draw_progress(0)
        self._set_ctrl_state(start=True, pause=False, reset=True)

    def reset_animation(self):
        self._stop_animation()
        self._draw_progress(0)
        self.current_qr_index = 0
        self._show_current()
        self._set_ctrl_state(start=True, pause=False, reset=True)

    # ── 프로그레스 애니메이션 ─────────────────────────────

    def _start_progress(self):
        self._draw_progress(0)
        self.progress_start_time = time.time()
        self._update_progress()

    def _update_progress(self):
        if not self.is_playing:
            return
        elapsed_ms = (time.time() - self.progress_start_time) * 1000
        fraction = elapsed_ms / self.get_interval_ms()

        if fraction < 1.0:
            self._draw_progress(fraction)
            self.animation_job = self.win.after(20, self._update_progress)
        else:
            self._draw_progress(1.0)
            self.animation_job = self.win.after(0, self._advance)

    def _advance(self):
        if not self.is_playing:
            return
        if self.current_qr_index == len(self.qr_images) - 1:
            # 마지막 QR → 정지, 시작 버튼 다시 활성화 (처음부터 재시작 가능)
            self._stop_animation()
            self._draw_progress(0)
            self._set_ctrl_state(start=True, pause=False, reset=True)
            return
        self.current_qr_index += 1
        self._show_current()
        self._start_progress()


# ════════════════════════════════════════════════════════
#  메인 창
# ════════════════════════════════════════════════════════

class QRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("QR 코드 생성기")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.player_win = None

        outer = tk.Frame(root, bg=BG, padx=20, pady=18)
        outer.pack()

        # ── 타이틀 ───────────────────────────────────────
        tk.Label(outer, text="QR 코드 생성기",
                 bg=BG, fg=TEXT, font=(FONT, 14, "bold")
                 ).pack(anchor='w', pady=(0, 14))

        # ── 입력 카드 ────────────────────────────────────
        input_card = tk.Frame(outer, bg=CARD,
                              highlightbackground=BORDER, highlightthickness=1)
        input_card.pack(fill=tk.X, pady=(0, 10))
        inner_input = tk.Frame(input_card, bg=CARD, padx=12, pady=12)
        inner_input.pack(fill=tk.X)

        tk.Label(inner_input, text="텍스트 입력",
                 bg=CARD, fg=TEXT_MUTED, font=(FONT, 9)).pack(anchor='w', pady=(0, 4))

        text_frame = tk.Frame(inner_input, bg=CARD,
                              highlightbackground=BORDER, highlightthickness=1)
        text_frame.pack(fill=tk.X)

        scrollbar = tk.Scrollbar(text_frame, bg=BG)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_area = tk.Text(
            text_frame, width=68, height=22,
            yscrollcommand=scrollbar.set,
            font=(FONT, 10), bg=CARD, fg=TEXT,
            relief=tk.FLAT, bd=8,
            insertbackground=PRIMARY,
            selectbackground=PRIMARY
        )
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH)
        scrollbar.config(command=self.text_area.yview)
        self.text_area.bind('<KeyRelease>', self.update_char_count)

        count_row = tk.Frame(inner_input, bg=CARD)
        count_row.pack(fill=tk.X, pady=(4, 0))
        self.char_label = tk.Label(count_row, text="0 글자",
                                   bg=CARD, fg=TEXT_MUTED, font=(FONT, 9))
        self.char_label.pack(side=tk.RIGHT)

        # ── 버튼 행 ──────────────────────────────────────
        btn_row = tk.Frame(outer, bg=BG)
        btn_row.pack(fill=tk.X, pady=(0, 4))

        styled_btn(btn_row, "QR 생성", self.generate_qr,
                   PRIMARY, PRIMARY_HOV, width=12).pack(side=tk.LEFT, padx=(0, 6))
        styled_btn(btn_row, "닫기", root.destroy,
                   DANGER, DANGER_HOV, width=8).pack(side=tk.LEFT)

        # 전환 간격 (메인에서도 조절 가능, 재생 창과 공유)
        self.speed_var = tk.StringVar(value="0.5")
        speed_row = tk.Frame(outer, bg=BG)
        speed_row.pack(anchor='e', pady=(4, 0))
        tk.Label(speed_row, text="전환 간격",
                 bg=BG, fg=TEXT_MUTED, font=(FONT, 9)).pack(side=tk.LEFT)
        tk.Spinbox(
            speed_row, from_=0.1, to=10.0, increment=0.1,
            textvariable=self.speed_var, width=5,
            format="%.1f", font=(FONT, 10),
            bg=CARD, fg=TEXT, relief=tk.FLAT,
            highlightbackground=BORDER, highlightthickness=1,
            buttonbackground=BG
        ).pack(side=tk.LEFT, padx=6)
        tk.Label(speed_row, text="초", bg=BG, fg=TEXT_MUTED, font=(FONT, 9)).pack(side=tk.LEFT)

    # ── 이벤트 ────────────────────────────────────────────

    def update_char_count(self, event=None):
        text = self.text_area.get("1.0", "end-1c")
        self.char_label.config(text=f"{len(text)} 글자")

    def generate_qr(self):
        text = self.text_area.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showwarning("경고", "텍스트를 입력해주세요.")
            return

        chunks = split_text_by_newlines(text)

        qr_images = []
        for i, chunk in enumerate(chunks):
            content = f"\n# {i + 1}번째\n{chunk}\n"
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=6, border=4,
            )
            qr.add_data(content.encode('utf-8'))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            img = img.resize((360, 360), RESAMPLE)
            qr_images.append(ImageTk.PhotoImage(img))

        # 기존 재생 창이 열려 있으면 닫기
        if self.player_win and self.player_win.win.winfo_exists():
            self.player_win._stop_animation()
            self.player_win.win.destroy()

        # 새 재생 창 열기
        self.player_win = QRPlayerWindow(self.root, qr_images, self.speed_var)


if __name__ == "__main__":
    root = tk.Tk()
    app = QRApp(root)
    root.mainloop()
