; C3-1 블럭 생성
(if (not (tblsearch "BLOCK" "C3-1"))
    (progn
      ;; 반지름 150인 원에 내접하는 정삼각형의 외접원(r=150)에 내접하는 5각 별
      ;; 꼭짓점은 90도(위쪽)부터 72도 간격, 별 연결 순서: 0→2→4→1→3
      (setq r 150)
      (setq pt0 (list (* r (cos (* pi 0.5)))                    (* r (sin (* pi 0.5)))                    0)) ; 90°
      (setq pt1 (list (* r (cos (+ (* pi 0.5) (* 2 (/ pi 5))))) (* r (sin (+ (* pi 0.5) (* 2 (/ pi 5))))) 0)) ; 162°
      (setq pt2 (list (* r (cos (+ (* pi 0.5) (* 4 (/ pi 5))))) (* r (sin (+ (* pi 0.5) (* 4 (/ pi 5))))) 0)) ; 234°
      (setq pt3 (list (* r (cos (+ (* pi 0.5) (* 6 (/ pi 5))))) (* r (sin (+ (* pi 0.5) (* 6 (/ pi 5))))) 0)) ; 306°
      (setq pt4 (list (* r (cos (+ (* pi 0.5) (* 8 (/ pi 5))))) (* r (sin (+ (* pi 0.5) (* 8 (/ pi 5))))) 0)) ; 18°
      ;; 별 모양: 한 꼭짓점 건너뛰며 연결 (0→2→4→1→3→닫기)
      (command "_.PLINE" pt0 pt2 pt4 pt1 pt3 "_C")
      (command "_.-BLOCK" "C3-1" '(0 0 0) (entlast) "")
      ;(princ "\n▶ [C3-1] 블럭 생성 완료.")
    )
    ;(princ "\n▶ [C3-1] 블럭은 이미 존재하여 건너뜁니다.")
  )
