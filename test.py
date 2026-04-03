(defun c:BLK_BOUND_FIX (/ ent obj insPt rot sx sy sz blkName blkDef 
                          allMin allMax oName tmpMin tmpMax p1 p2 p3 p4)
  (vl-load-com)

  ;; 1. 블록 선택
  (setq ent (car (entsel "\n블록을 선택하세요: ")))
  
  (if (and ent (= (cdr (assoc 0 (entget ent))) "INSERT"))
    (progn
      (setq obj (vlax-ename->vla-object ent)
            insPt (vlax-safearray->list (vlax-variant-value (vla-get-InsertionPoint obj)))
            rot (vla-get-Rotation obj)
            ;; [수정] 축척은 X, Y, Z 각각 가져와야 함
            sx (vla-get-ScaleFactorX obj)
            sy (vla-get-ScaleFactorY obj)
            sz (vla-get-ScaleFactorZ obj)
            blkName (vla-get-Name obj)
            blkDef (vla-item (vla-get-blocks (vla-get-activedocument (vlax-get-acad-object))) blkName)
            allMin nil
            allMax nil)

      ;; 2. 블록 내부 객체 순회 (OLE, HATCH 제외)
      (vlax-for subObj blkDef
        (setq oName (vla-get-ObjectName subObj))
        ;; OLE와 Hatch는 계산에서 완전히 제외
        (if (not (or (wcmatch oName "AcDbOle*") (wcmatch oName "AcDbHatch")))
          (if (not (vl-catch-all-error-p (vl-catch-all-apply 'vla-getboundingbox (list subObj 'tmpMin 'tmpMax))))
            (progn
              (setq minL (vlax-safearray->list tmpMin)
                    maxL (vlax-safearray->list tmpMax))
              
              (if (null allMin)
                (setq allMin minL allMax maxL)
                (setq allMin (mapcar 'min allMin minL)
                      allMax (mapcar 'max allMax maxL))
              )
            )
          )
        )
      )

      ;; 3. 좌표 변환 및 출력
      (if (and allMin allMax)
        (let ( (tr-pt (lambda (pt)
                        (let* ((x (* (car pt) sx))
                               (y (* (cadr pt) sy))
                               (nx (+ (- (* x (cos rot)) (* y (sin rot))) (car insPt)))
                               (ny (+ (+ (* x (sin rot)) (* y (cos rot))) (cadr insPt))))
                          (list nx ny (+ (caddr pt) (caddr insPt)))))) )
          
          (setq p1 (tr-pt allMin) ;; 좌하
                p2 (tr-pt (list (car allMax) (cadr allMin) (caddr allMin))) ;; 우하
                p3 (tr-pt allMax) ;; 우상
                p4 (tr-pt (list (car allMin) (cadr allMax) (caddr allMin)))) ;; 좌상

          (princ "\n--- [추출된 실제 좌표] ---")
          (princ (strcat "\n좌측 하단: " (vl-prin1-to-string p1)))
          (princ (strcat "\n우측 하단: " (vl-prin1-to-string p2)))
          (princ (strcat "\n우측 상단: " (vl-prin1-to-string p3)))
          (princ (strcat "\n좌측 상단: " (vl-prin1-to-string p4)))
        )
        (princ "\n오류: OLE/해치를 제외하면 블록 내에 계산 가능한 객체가 없습니다.")
      )
    )
    (princ "\n블록(INSERT) 객체가 아닙니다.")
  )
  (princ)
)