import tkinter as tk
from tkinter import messagebox
import qrcode
from PIL import Image, ImageTk

# QR코드 한 장당 최대 바이트 수 (헤더 제외)
MAX_BYTES = 2000

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS


def split_text_by_newlines(text, max_bytes=MAX_BYTES):
    """줄바꿈 경계에서 텍스트를 분할하여 각 청크가 max_bytes 이하가 되도록 함"""
    lines = text.split('\n')
    chunks = []
    current_lines = []
    current_bytes = 0

    for line in lines:
        line_bytes = len((line + '\n').encode('utf-8'))
        if current_lines and current_bytes + line_bytes > max_bytes:
            chunks.append('\n'.join(current_lines))
            current_lines = [line]
            current_bytes = line_bytes
        else:
            current_lines.append(line)
            current_bytes += line_bytes

    if current_lines:
        chunks.append('\n'.join(current_lines))

    return chunks


class QRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("QR 코드 생성기")
        self.root.resizable(False, False)
        self.qr_images = []
        self.current_qr_index = 0
        self.animation_job = None
        self.is_playing = False

        main_frame = tk.Frame(root, padx=15, pady=15)
        main_frame.pack()

        tk.Label(main_frame, text="텍스트 입력:", font=("맑은 고딕", 10)).pack(anchor='w')

        text_frame = tk.Frame(main_frame)
        text_frame.pack()

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_area = tk.Text(
            text_frame, width=50, height=10,
            yscrollcommand=scrollbar.set,
            font=("맑은 고딕", 10)
        )
        self.text_area.pack(side=tk.LEFT)
        scrollbar.config(command=self.text_area.yview)
        self.text_area.bind('<KeyRelease>', self.update_char_count)

        self.char_label = tk.Label(main_frame, text="0 글자", fg='gray', font=("맑은 고딕", 9))
        self.char_label.pack(anchor='e')

        # QR 생성 / 닫기
        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(pady=(8, 4))
        tk.Button(
            btn_frame, text="QR 생성", command=self.generate_qr,
            width=10, font=("맑은 고딕", 10)
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            btn_frame, text="닫기", command=root.destroy,
            width=10, font=("맑은 고딕", 10)
        ).pack(side=tk.LEFT, padx=5)

        # 순환 제어 버튼 + 속도 입력
        ctrl_frame = tk.Frame(main_frame)
        ctrl_frame.pack(pady=(0, 8))

        self.btn_start = tk.Button(
            ctrl_frame, text="시작", command=self.start_animation,
            width=8, font=("맑은 고딕", 10), state=tk.DISABLED
        )
        self.btn_start.pack(side=tk.LEFT, padx=3)

        self.btn_pause = tk.Button(
            ctrl_frame, text="일시정지", command=self.pause_animation,
            width=8, font=("맑은 고딕", 10), state=tk.DISABLED
        )
        self.btn_pause.pack(side=tk.LEFT, padx=3)

        self.btn_reset = tk.Button(
            ctrl_frame, text="처음으로", command=self.reset_animation,
            width=8, font=("맑은 고딕", 10), state=tk.DISABLED
        )
        self.btn_reset.pack(side=tk.LEFT, padx=3)

        # 속도 조절
        speed_frame = tk.Frame(main_frame)
        speed_frame.pack(pady=(0, 4))

        tk.Label(speed_frame, text="전환 간격:", font=("맑은 고딕", 9)).pack(side=tk.LEFT)
        self.speed_var = tk.StringVar(value="0.5")
        self.speed_entry = tk.Spinbox(
            speed_frame, from_=0.1, to=10.0, increment=0.1,
            textvariable=self.speed_var, width=5,
            format="%.1f", font=("맑은 고딕", 9)
        )
        self.speed_entry.pack(side=tk.LEFT, padx=3)
        tk.Label(speed_frame, text="초", font=("맑은 고딕", 9)).pack(side=tk.LEFT)

        # QR 표시 영역
        self.qr_label = tk.Label(main_frame, bg='white')
        self.qr_label.pack(pady=(5, 0))

        self.page_label = tk.Label(main_frame, text="", fg='gray', font=("맑은 고딕", 9))
        self.page_label.pack()

    def update_char_count(self, event=None):
        text = self.text_area.get("1.0", "end-1c")
        self.char_label.config(text=f"{len(text)} 글자")

    def get_interval_ms(self):
        try:
            val = float(self.speed_var.get())
            return max(100, int(val * 1000))
        except ValueError:
            return 500

    def generate_qr(self):
        text = self.text_area.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showwarning("경고", "텍스트를 입력해주세요.")
            return

        self._stop_animation()

        chunks = split_text_by_newlines(text)

        self.qr_images = []
        for i, chunk in enumerate(chunks):
            content = f"\n# {i + 1}번째\n{chunk}\n"
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=5,
                border=4,
            )
            qr.add_data(content.encode('utf-8'))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            img = img.resize((300, 300), RESAMPLE)
            self.qr_images.append(ImageTk.PhotoImage(img))

        self.current_qr_index = 0
        self._show_current()

        # 버튼 활성화
        has_multi = len(self.qr_images) > 1
        self.btn_start.config(state=tk.NORMAL if has_multi else tk.DISABLED)
        self.btn_pause.config(state=tk.DISABLED)
        self.btn_reset.config(state=tk.NORMAL if has_multi else tk.DISABLED)

    def _show_current(self):
        if not self.qr_images:
            return
        self.qr_label.config(image=self.qr_images[self.current_qr_index])
        self.page_label.config(text=f"{self.current_qr_index + 1} / {len(self.qr_images)}")

    def _stop_animation(self):
        if self.animation_job:
            self.root.after_cancel(self.animation_job)
            self.animation_job = None
        self.is_playing = False

    def start_animation(self):
        if not self.qr_images or self.is_playing:
            return
        self.is_playing = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_pause.config(state=tk.NORMAL)
        self._tick()

    def pause_animation(self):
        self._stop_animation()
        self.btn_start.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED)

    def reset_animation(self):
        self._stop_animation()
        self.current_qr_index = 0
        self._show_current()
        self.btn_start.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED)

    def _tick(self):
        if not self.is_playing or not self.qr_images:
            return
        self._show_current()
        self.current_qr_index = (self.current_qr_index + 1) % len(self.qr_images)
        self.animation_job = self.root.after(self.get_interval_ms(), self._tick)


if __name__ == "__main__":
    root = tk.Tk()
    app = QRApp(root)
    root.mainloop()
