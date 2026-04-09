; C3-1 블럭 생성 (내부 교차선 없는 5각 별 외곽선)
(if (not (tblsearch "BLOCK" "C3-1"))
    (progn
      (setq r     150)
      (setq r-in  (* r (/ 2.0 (+ 3.0 (sqrt 5.0))))) ; 내부 반지름 ≈ 57.3
      ;; 외부점(r)과 내부점(r-in)을 36° 간격으로 교대 배치 → 10개 꼭짓점
      (setq pts (list))
      (setq i 0)
      (repeat 10
        (setq ang (+ (/ pi 2) (* i (/ pi 5)))) ; 90°부터 36° 간격
        (setq cur-r (if (= (rem i 2) 0) r r-in)) ; 짝수: 외부, 홀수: 내부
        (setq pts (append pts (list (list (* cur-r (cos ang)) (* cur-r (sin ang)) 0))))
        (setq i (1+ i))
      )
      (apply 'command (append (list "_.PLINE") pts (list "_C")))
      (command "_.-BLOCK" "C3-1" '(0 0 0) (entlast) "")
      ;(princ "\n▶ [C3-1] 블럭 생성 완료.")
    )
    ;(princ "\n▶ [C3-1] 블럭은 이미 존재하여 건너뜁니다.")
  )
