import tkinter as tk
from tkinter import messagebox
import time
import winreg
import ctypes
import qrcode
from PIL import Image, ImageTk

# ── Windows API로 제목표시줄만 제거 (작업표시줄은 유지) ──
_u32 = ctypes.windll.user32
_GWL_STYLE       = -16
_GWL_EXSTYLE     = -20
_WS_CAPTION      = 0x00C00000
_WS_THICKFRAME   = 0x00040000
_WS_EX_APPWINDOW  = 0x00040000
_WS_EX_TOOLWINDOW = 0x00000080
_SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0020  # NOSIZE|NOMOVE|NOZORDER|FRAMECHANGED
_GA_ROOT = 2

def hide_titlebar(window, show_in_taskbar=True):
    """제목표시줄 제거. show_in_taskbar=False 이면 작업표시줄에도 숨김."""
    window.update_idletasks()
    hwnd = _u32.GetAncestor(window.winfo_id(), _GA_ROOT)
    style = _u32.GetWindowLongW(hwnd, _GWL_STYLE)
    style &= ~(_WS_CAPTION | _WS_THICKFRAME)
    _u32.SetWindowLongW(hwnd, _GWL_STYLE, style)
    ex = _u32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
    if show_in_taskbar:
        ex = (ex & ~_WS_EX_TOOLWINDOW) | _WS_EX_APPWINDOW
    else:
        ex = (ex & ~_WS_EX_APPWINDOW) | _WS_EX_TOOLWINDOW
    _u32.SetWindowLongW(hwnd, _GWL_EXSTYLE, ex)
    _u32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, _SWP_FLAGS)


def make_app_icon():
    """작업표시줄·창 아이콘용 이미지 생성 (QR 패턴 모양)"""
    from PIL import ImageDraw
    sz, c, bg = 64, "#2D3748", "#FFFFFF"
    img = Image.new("RGB", (sz, sz), bg)
    d = ImageDraw.Draw(img)
    # 테두리
    d.rectangle([0, 0, sz-1, sz-1], fill="#4F86F0")
    # 흰 배경
    d.rectangle([4, 4, sz-5, sz-5], fill=bg)
    # 좌상단 파인더
    d.rectangle([7, 7, 24, 24], outline=c, width=2)
    d.rectangle([11, 11, 20, 20], fill=c)
    # 우상단 파인더
    d.rectangle([39, 7, 56, 24], outline=c, width=2)
    d.rectangle([43, 11, 52, 20], fill=c)
    # 좌하단 파인더
    d.rectangle([7, 39, 24, 56], outline=c, width=2)
    d.rectangle([11, 43, 20, 52], fill=c)
    # 데이터 도트
    for x, y in [(29,7),(34,7),(29,12),(34,17),(7,29),(12,29),(17,34),(29,29),(34,34),(29,39),(39,34),(44,29),(49,34),(44,39),(49,44),(39,49),(44,49)]:
        d.rectangle([x, y, x+3, y+3], fill=c)
    return img

MAX_BYTES = 2000
REG_KEY   = r"Software\SHI AI\QRGenerator"

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


# ── 레지스트리 유틸 ──────────────────────────────────────

def reg_save_pos(x, y):
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY)
        winreg.SetValueEx(key, "x", 0, winreg.REG_SZ, str(x))
        winreg.SetValueEx(key, "y", 0, winreg.REG_SZ, str(y))
        winreg.CloseKey(key)
    except Exception:
        pass


def reg_load_pos():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY)
        x = int(winreg.QueryValueEx(key, "x")[0])
        y = int(winreg.QueryValueEx(key, "y")[0])
        winreg.CloseKey(key)
        return x, y
    except Exception:
        return None


# ── 텍스트 분할 ──────────────────────────────────────────

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


# ── 공통 버튼 팩토리 ────────────────────────────────────

def styled_btn(parent, text, command, bg, hover, state=tk.NORMAL):
    btn = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=CARD, activebackground=hover, activeforeground=CARD,
        relief=tk.FLAT, bd=0, cursor="hand2",
        font=(FONT, 10, "bold"),
        padx=8, pady=8, state=state,
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
    return btn


def restore_btn_color(btn):
    btn.config(bg=btn._base_bg)


def make_draggable(widget, window):
    """위젯을 드래그해 window를 이동할 수 있도록 바인딩"""
    def on_press(e):
        widget._drag_x = e.x_root - window.winfo_x()
        widget._drag_y = e.y_root - window.winfo_y()
    def on_drag(e):
        window.geometry(f"+{e.x_root - widget._drag_x}+{e.y_root - widget._drag_y}")
    widget.bind("<ButtonPress-1>", on_press)
    widget.bind("<B1-Motion>", on_drag)


# ════════════════════════════════════════════════════════
#  QR 재생 창
# ════════════════════════════════════════════════════════

class QRPlayerWindow:
    def __init__(self, parent_root, qr_images):
        self.parent_root = parent_root
        self.qr_images   = qr_images
        self.current_qr_index    = 0
        self.animation_job       = None
        self.is_playing          = False
        self.is_paused           = False
        self.progress_start_time = 0.0
        self.paused_elapsed_ms   = 0.0

        self.win = tk.Toplevel(parent_root)
        self.win.configure(bg=BG)

        outer = tk.Frame(self.win, bg=BG, padx=20, pady=18)
        outer.pack()

        # ── 타이틀 행 (드래그 이동) ──────────────────────
        title_row = tk.Frame(outer, bg=BG)
        title_row.pack(fill=tk.X, pady=(0, 12))
        title_lbl = tk.Label(title_row, text="QR 재생",
                             bg=BG, fg=TEXT, font=(FONT, 13, "bold"))
        title_lbl.pack(side=tk.LEFT)
        tk.Label(title_row, text=f"총 {len(qr_images)}장",
                 bg=BG, fg=TEXT_MUTED, font=(FONT, 10)).pack(side=tk.LEFT, padx=(8, 0))
        make_draggable(title_lbl, self.win)
        make_draggable(title_row, self.win)

        # ── QR 표시 카드 ─────────────────────────────────
        qr_card = tk.Frame(outer, bg=CARD,
                           highlightbackground=BORDER, highlightthickness=1)
        qr_card.pack(fill=tk.X, pady=(0, 10))

        self.qr_label = tk.Label(qr_card, bg=CARD, width=380, height=380)
        self.qr_label.pack(padx=14, pady=(14, 6))

        self.page_label = tk.Label(qr_card, text="",
                                   bg=CARD, fg=TEXT_MUTED, font=(FONT, 11))
        self.page_label.pack(pady=(0, 8))

        # 프로그레스 바
        pg_frame = tk.Frame(qr_card, bg=CARD, padx=14)
        pg_frame.pack(fill=tk.X, pady=(0, 14))
        self.progress_canvas = tk.Canvas(
            pg_frame, height=8, bg=PROGRESS_BG,
            highlightthickness=0, bd=0
        )
        self.progress_canvas.pack(fill=tk.X)
        self.progress_fill = self.progress_canvas.create_rectangle(
            0, 0, 0, 8, fill=PROGRESS_FG, outline=""
        )

        # ── 재생 제어 카드 ───────────────────────────────
        ctrl_card = tk.Frame(outer, bg=CARD,
                             highlightbackground=BORDER, highlightthickness=1)
        ctrl_card.pack(fill=tk.X, pady=(0, 10))
        inner_ctrl = tk.Frame(ctrl_card, bg=CARD, padx=12, pady=12)
        inner_ctrl.pack(fill=tk.X)

        # 버튼 4개 – 시작/일시정지/처음으로(넓게) + 닫기(좁게)
        ctrl_btn_row = tk.Frame(inner_ctrl, bg=CARD)
        ctrl_btn_row.pack(fill=tk.X)

        has_multi = len(qr_images) > 1
        self.btn_start = styled_btn(
            ctrl_btn_row, "▶  시작", self.start_animation,
            CTRL, CTRL_HOV, state=tk.NORMAL if has_multi else tk.DISABLED
        )
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

        self.btn_pause = styled_btn(
            ctrl_btn_row, "⏸  일시정지", self.pause_animation,
            NEUTRAL, NEUTRAL_HOV, state=tk.DISABLED
        )
        self.btn_pause.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

        self.btn_reset = styled_btn(
            ctrl_btn_row, "↩  처음으로", self.reset_animation,
            NEUTRAL, NEUTRAL_HOV, state=tk.NORMAL if has_multi else tk.DISABLED
        )
        self.btn_reset.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

        # 닫기 – 고정 너비로 작게
        styled_btn(
            ctrl_btn_row, "✕", self._on_close,
            DANGER, DANGER_HOV
        ).pack(side=tk.LEFT, ipadx=6)

        # 속도 조절
        speed_row = tk.Frame(inner_ctrl, bg=CARD)
        speed_row.pack(fill=tk.X, pady=(10, 0))
        tk.Label(speed_row, text="전환 간격",
                 bg=CARD, fg=TEXT_MUTED, font=(FONT, 9)).pack(side=tk.LEFT)
        self.speed_var = tk.StringVar(value="0.5")
        tk.Spinbox(
            speed_row, from_=0.1, to=10.0, increment=0.1,
            textvariable=self.speed_var, width=5,
            format="%.1f", font=(FONT, 10),
            bg=CARD, fg=TEXT, relief=tk.FLAT,
            highlightbackground=BORDER, highlightthickness=1,
            buttonbackground=BG
        ).pack(side=tk.LEFT, padx=6)
        tk.Label(speed_row, text="초", bg=CARD, fg=TEXT_MUTED, font=(FONT, 9)).pack(side=tk.LEFT)

        # 첫 QR 표시 후 창 위치 지정, 제목표시줄 제거
        self._show_current()
        self.win.update_idletasks()
        self._place_relative_to_parent()
        self.win.after(50, lambda: hide_titlebar(self.win, show_in_taskbar=False))

    # ── 위치 지정 ────────────────────────────────────────

    def _place_relative_to_parent(self):
        px = self.parent_root.winfo_x()
        py = self.parent_root.winfo_y()
        pw = self.parent_root.winfo_width()
        wx = px + pw + 12
        wy = py
        self.win.geometry(f"+{wx}+{wy}")

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
            w = 380
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
        if self.is_paused:
            # 일시정지된 위치에서 재개
            self.is_paused = False
            self.is_playing = True
            self._set_ctrl_state(start=False, pause=True, reset=True)
            # 이미 흐른 시간을 반영해 시작 시각 역산
            self.progress_start_time = time.time() - self.paused_elapsed_ms / 1000.0
            self._update_progress()
        else:
            # 완료 후 또는 처음 → 1번째부터 새로 시작
            self.is_paused = False
            self.paused_elapsed_ms = 0.0
            self.current_qr_index = 0
            self._show_current()
            self.is_playing = True
            self._set_ctrl_state(start=False, pause=True, reset=True)
            self._start_progress()

    def pause_animation(self):
        # 현재까지 흐른 시간 저장
        self.paused_elapsed_ms = (time.time() - self.progress_start_time) * 1000.0
        self.is_paused = True
        self._stop_animation()
        # 프로그레스 바 현재 상태 유지 (리셋 안 함)
        self._set_ctrl_state(start=True, pause=False, reset=True)

    def reset_animation(self):
        self.is_paused = False
        self.paused_elapsed_ms = 0.0
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
        elapsed_ms = (time.time() - self.progress_start_time) * 1000.0
        fraction   = elapsed_ms / self.get_interval_ms()

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
            # 마지막 QR → 완료
            self._stop_animation()
            self._draw_progress(0)
            self.is_paused = False
            self._set_ctrl_state(start=True, pause=False, reset=True)
            return
        self.current_qr_index += 1
        self._show_current()
        self._start_progress()


# ════════════════════════════════════════════════════════
#  메인 생성기 창
# ════════════════════════════════════════════════════════

class QRApp:
    def __init__(self, root):
        self.root       = root
        self.player_win = None
        self.root.title("QR 코드 생성기")
        self.root.configure(bg=BG)
        # 아이콘 설정
        self._icon = ImageTk.PhotoImage(make_app_icon())
        self.root.iconphoto(True, self._icon)

        outer = tk.Frame(root, bg=BG, padx=20, pady=18)
        outer.pack()

        # ── 타이틀 행 (드래그 이동) ──────────────────────
        title_row = tk.Frame(outer, bg=BG)
        title_row.pack(fill=tk.X, pady=(0, 14))
        title_lbl = tk.Label(title_row, text="QR 코드 생성기",
                             bg=BG, fg=TEXT, font=(FONT, 14, "bold"))
        title_lbl.pack(anchor='w')
        make_draggable(title_lbl, self.root)
        make_draggable(title_row, self.root)

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
            text_frame, width=68, height=26,
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

        # ── 버튼 행 – 전체 너비 채움 ─────────────────────
        btn_row = tk.Frame(outer, bg=BG)
        btn_row.pack(fill=tk.X, pady=(0, 4))

        styled_btn(btn_row, "QR 생성", self.generate_qr,
                   PRIMARY, PRIMARY_HOV).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        styled_btn(btn_row, "닫기", self._on_close,
                   DANGER, DANGER_HOV).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── 저장된 위치 복원 + 제목표시줄 제거 ──────────
        pos = reg_load_pos()
        if pos:
            self.root.update_idletasks()
            self.root.geometry(f"+{pos[0]}+{pos[1]}")
        self.root.after(50, lambda: hide_titlebar(self.root))
        self.root.bind("<FocusIn>", self._on_main_focus)

    # ── 이벤트 ────────────────────────────────────────────

    def _on_main_focus(self, event=None):
        """메인 창이 포커스를 받으면 재생 창을 앞으로 올림"""
        if (self.player_win
                and self.player_win.win.winfo_exists()):
            self.player_win.win.lift()
            self.player_win.win.focus_force()

    def update_char_count(self, event=None):
        text = self.text_area.get("1.0", "end-1c")
        self.char_label.config(text=f"{len(text)} 글자")

    def _on_close(self):
        self.root.update_idletasks()
        reg_save_pos(self.root.winfo_x(), self.root.winfo_y())
        self.root.destroy()

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
            img = img.resize((380, 380), RESAMPLE)
            qr_images.append(ImageTk.PhotoImage(img))

        # 기존 재생 창 닫기
        if self.player_win and self.player_win.win.winfo_exists():
            self.player_win._stop_animation()
            self.player_win.win.destroy()

        self.player_win = QRPlayerWindow(self.root, qr_images)


if __name__ == "__main__":
    root = tk.Tk()
    app = QRApp(root)
    root.mainloop()
