(defun c:BLK_BOUND_FIX (/ ent obj insPt rot sx sy sz blkName blkDef 
                          allMin allMax oName tmpMin tmpMax p1 p2 p3 p4 tr-pt)
  (vl-load-com)

  ;; 1. 블록 선택
  (setq ent (car (entsel "\n블록을 선택하세요: ")))
  
  (if (and ent (= (cdr (assoc 0 (entget ent))) "INSERT"))
    (progn
      (setq obj (vlax-ename->vla-object ent))
      
      ;; [수정] 2018 버전 및 범용성을 위해 vlax-get-property 사용
      (setq insPt (vlax-safearray->list (vlax-variant-value (vlax-get-property obj 'InsertionPoint)))
            rot   (vlax-get-property obj 'Rotation)
            sx    (vlax-get-property obj 'XScaleFactor)
            sy    (vlax-get-property obj 'YScaleFactor)
            sz    (vlax-get-property obj 'ZScaleFactor)
            blkName (vlax-get-property obj 'Name)
            blkDef (vla-item (vla-get-blocks (vla-get-activedocument (vlax-get-acad-object))) blkName)
            allMin nil
            allMax nil)

      ;; 2. 블록 내부 객체 순회 (OLE, HATCH 제외)
      (vlax-for subObj blkDef
        (setq oName (vla-get-ObjectName subObj))
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

      ;; 3. 좌표 변환 함수 정의 (회전, 축척, 이동 적용)
      (setq tr-pt (lambda (pt)
                    (let* ((x (* (car pt) sx))
                           (y (* (cadr pt) sy))
                           (nx (+ (- (* x (cos rot)) (* y (sin rot))) (car insPt)))
                           (ny (+ (+ (* x (sin rot)) (* y (cos rot))) (cadr insPt))))
                      (list nx ny (+ (* (caddr pt) sz) (caddr insPt))))))

      ;; 4. 결과 도출 및 출력
      (if (and allMin allMax)
        (progn
          (setq p1 (apply tr-pt (list allMin)) ;; 좌하
                p2 (apply tr-pt (list (list (car allMax) (cadr allMin) (caddr allMin)))) ;; 우하
                p3 (apply tr-pt (list allMax)) ;; 우상
                p4 (apply tr-pt (list (list (car allMin) (cadr allMax) (caddr allMin))))) ;; 좌상

          (princ "\n--- [OLE/해치 제외 추출 결과] ---")
          (princ (strcat "\n좌하단 (P1): " (vl-prin1-to-string p1)))
          (princ (strcat "\n우하단 (P2): " (vl-prin1-to-string p2)))
          (princ (strcat "\n우상단 (P3): " (vl-prin1-to-string p3)))
          (princ (strcat "\n좌상단 (P4): " (vl-prin1-to-string p4)))
        )
        (princ "\n오류: 블록 내에 계산 가능한 일반 객체(선, 원 등)가 없습니다.")
      )
    )
    (princ "\n블록(INSERT) 객체가 아닙니다.")
  )
  (princ)
)