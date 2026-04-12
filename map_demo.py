"""
주소 지도 시각화 - Python Desktop App
의존 패키지: pip install tkintermapview customtkinter
"""

import tkinter as tk
import customtkinter as ctk
import tkintermapview

# ── 샘플 주소 데이터 ────────────────────────────────────────────────
LOCATIONS = [
    {"name": "서울시청",          "address": "서울특별시 중구 세종대로 110",        "lat": 37.5663, "lng": 126.9779, "color": "#e53935"},
    {"name": "경복궁",            "address": "서울특별시 종로구 사직로 161",          "lat": 37.5796, "lng": 126.9770, "color": "#8e24aa"},
    {"name": "강남역",            "address": "서울특별시 강남구 강남대로 396",        "lat": 37.4979, "lng": 127.0276, "color": "#1e88e5"},
    {"name": "상암 월드컵경기장", "address": "서울특별시 마포구 월드컵북로 396",     "lat": 37.5683, "lng": 126.8971, "color": "#43a047"},
    {"name": "롯데월드타워",      "address": "서울특별시 송파구 올림픽로 300",       "lat": 37.5126, "lng": 127.1021, "color": "#fb8c00"},
    {"name": "인천국제공항",      "address": "인천광역시 중구 공항로 272",           "lat": 37.4602, "lng": 126.4407, "color": "#00897b"},
]
# ───────────────────────────────────────────────────────────────────


class MapApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ── 윈도우 기본 설정 ──
        self.title("📍 주소 지도 시각화")
        self.geometry("1100x680")
        self.minsize(800, 500)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.selected_index = None
        self._build_ui()
        self._place_markers()

        # 전체 위치가 보이도록 초기 뷰 설정
        center_lat = sum(l["lat"] for l in LOCATIONS) / len(LOCATIONS)
        center_lng = sum(l["lng"] for l in LOCATIONS) / len(LOCATIONS)
        self.map_widget.set_position(center_lat, center_lng)
        self.map_widget.set_zoom(10)

    # ── UI 구성 ───────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── 헤더 ──
        header = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color="#1a73e8")
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="📍  주소 지도 시각화",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="white"
        ).grid(row=0, column=0, padx=20, pady=10, sticky="w")

        ctk.CTkLabel(
            header, text=f"총 {len(LOCATIONS)}개 위치",
            font=ctk.CTkFont(size=12),
            text_color="#cce0ff"
        ).grid(row=0, column=1, padx=20, pady=10, sticky="e")

        # ── 사이드바 ──
        sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color="#ffffff")
        sidebar.grid(row=1, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            sidebar, text="위치 목록",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#888888"
        ).grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")

        # 스크롤 가능한 목록
        self.list_frame = ctk.CTkScrollableFrame(
            sidebar, fg_color="#ffffff", corner_radius=0
        )
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.list_frame.grid_columnconfigure(0, weight=1)

        self.list_buttons = []
        for i, loc in enumerate(LOCATIONS):
            btn = self._make_list_item(self.list_frame, i, loc)
            btn.grid(row=i, column=0, sticky="ew", padx=0, pady=0)
            self.list_buttons.append(btn)

        # ── 지도 ──
        self.map_widget = tkintermapview.TkinterMapView(
            self, corner_radius=0
        )
        self.map_widget.grid(row=1, column=1, sticky="nsew")

    def _make_list_item(self, parent, index, loc):
        """사이드바 개별 아이템 프레임 생성"""
        frame = ctk.CTkFrame(
            parent, corner_radius=0, fg_color="#ffffff",
            cursor="hand2"
        )
        frame.grid_columnconfigure(1, weight=1)

        # 컬러 인디케이터 바
        indicator = tk.Frame(frame, width=4, bg=loc["color"])
        indicator.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, 10), pady=8)

        # 번호 + 이름
        ctk.CTkLabel(
            frame,
            text=f"{index + 1}.  {loc['name']}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#222222",
            anchor="w"
        ).grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(10, 2))

        # 주소
        ctk.CTkLabel(
            frame,
            text=loc["address"],
            font=ctk.CTkFont(size=11),
            text_color="#888888",
            anchor="w",
            wraplength=210
        ).grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 10))

        # 구분선
        sep = tk.Frame(frame, height=1, bg="#f0f0f0")
        sep.grid(row=2, column=0, columnspan=2, sticky="ew")

        # 클릭 바인딩
        for widget in (frame, indicator, sep):
            widget.bind("<Button-1>", lambda e, idx=index: self._on_select(idx))
        for child in frame.winfo_children():
            child.bind("<Button-1>", lambda e, idx=index: self._on_select(idx))

        return frame

    # ── 마커 배치 ─────────────────────────────────────────────────
    def _place_markers(self):
        self.markers = []
        for i, loc in enumerate(LOCATIONS):
            marker = self.map_widget.set_marker(
                loc["lat"], loc["lng"],
                text=f"  {i + 1}. {loc['name']}",
                marker_color_circle=loc["color"],
                marker_color_outside=loc["color"],
                command=lambda m, idx=i: self._on_marker_click(idx)
            )
            self.markers.append(marker)

    # ── 이벤트 핸들러 ─────────────────────────────────────────────
    def _on_select(self, index):
        self._highlight_item(index)
        loc = LOCATIONS[index]
        self.map_widget.set_position(loc["lat"], loc["lng"])
        self.map_widget.set_zoom(15)

    def _on_marker_click(self, index):
        self._highlight_item(index)

    def _highlight_item(self, index):
        # 이전 선택 해제
        if self.selected_index is not None:
            self.list_buttons[self.selected_index].configure(fg_color="#ffffff")
            for child in self.list_buttons[self.selected_index].winfo_children():
                if isinstance(child, (ctk.CTkLabel,)):
                    child.configure(fg_color="#ffffff")

        # 새 선택 강조
        self.list_buttons[index].configure(fg_color="#e8f0fe")
        for child in self.list_buttons[index].winfo_children():
            if isinstance(child, ctk.CTkLabel):
                child.configure(fg_color="#e8f0fe")

        self.selected_index = index

        # 사이드바 스크롤 → 해당 아이템으로
        self.list_frame._parent_canvas.yview_moveto(
            index / max(len(LOCATIONS), 1)
        )


if __name__ == "__main__":
    app = MapApp()
    app.mainloop()
