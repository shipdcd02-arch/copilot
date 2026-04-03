(defun c:BLK_TEST (/ ent obj minpt maxpt err)
  (vl-load-com)
  (setq ent (car (entsel "\n블록 선택: ")))
  
  (if (and ent (= (cdr (assoc 0 (entget ent))) "INSERT"))
    (progn
      (setq obj (vlax-ename->vla-object ent))
      
      ;; 에러 발생 여부를 체크하며 실행
      (setq err (vl-catch-all-apply 'vla-getboundingbox (list obj 'minpt 'maxpt)))
      
      (if (vl-catch-all-error-p err)
        (progn
          (princ "\n[오류 발생] 이 블록은 범위를 계산할 수 없습니다.")
          (princ (strcat "\n상세 메시지: " (vl-catch-all-error-message err)))
          (princ "\n팁: 블록 내부에 무한선(XLINE)이 있거나 비어있는지 확인하세요.")
        )
        (progn
          (princ (strcat "\n좌하단: " (vl-prin1-to-string (vlax-safearray->list minpt))))
          (princ (strcat "\n우상단: " (vl-prin1-to-string (vlax-safearray->list maxpt))))
        )
      )
    )
  )
  (princ)
)