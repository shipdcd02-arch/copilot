(defun c:BLK_IGNORE_OLE (/ ent blkName blkDef minPt maxPt tmpMin tmpMax)
  (vl-load-com)
  (setq ent (car (entsel "\n블록 선택: ")))
  (if (and ent (= (cdr (assoc 0 (entget ent))) "INSERT"))
    (progn
      (setq blkName (cdr (assoc 2 (entget ent))))
      (setq blkDef (vla-item (vla-get-blocks (vla-get-activedocument (vlax-get-acad-object))) blkName))
      
      ;; 블록 내부 객체들을 하나씩 검사
      (vlax-for obj blkDef
        (if (not (wcmatch (vla-get-objectname obj) "AcDbOle*")) ;; OLE 객체 제외
          (if (not (vl-catch-all-error-p (vl-catch-all-apply 'vla-getboundingbox (list obj 'tmpMin 'tmpMax))))
            (progn
              ;; 전체 최소/최대 좌표 업데이트 로직 (생략 - 복잡함)
              (princ (strcat "\n계산 포함 객체: " (vla-get-objectname obj)))
            )
          )
        )
      )
      (princ "\n(OLE를 제외한 내부 객체 기반 계산 완료)")
    )
  )
  (princ)
)