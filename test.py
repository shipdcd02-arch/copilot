(defun c:BLK_BOUND_FIX (/ ent obj insPt rot sx sy sz blkName blkDef 
                          allMin allMax oName tmpMin tmpMax p1 p2 p3 p4 tr-pt)
  (vl-load-com)

  ;; 1. 블록 선택
  (setq ent (car (entsel "\n블록을 선택하세요: ")))
  
  (if (and ent (= (cdr (assoc 0 (entget ent))) "INSERT"))
    (progn
      (setq obj (vlax-ename->vla-object ent))
      
      ;; 블록 속성 추출 (2018 버전용 XScaleFactor 등 사용)
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

      ;; 3. 좌표 변환 함수 (tr-pt) 정의 - 직접 호출 방식으로 변경
      (defun my-transform (pt / x y nx ny)
        (setq x (* (car pt) sx)
              y (* (cadr pt) sy))
        (setq nx (+ (- (* x (cos rot)) (* y (sin rot))) (car insPt))
              ny (+ (+ (* x (sin rot)) (* y (cos rot))) (cadr insPt)))
        (list nx ny (+ (* (caddr pt) sz) (caddr insPt)))
      )

      ;; 4. 결과 도출 및 출력
      (if (and allMin allMax)
        (progn
          ;; 각 꼭지점 계산
          (setq p1 (my-transform allMin) ;; 좌하
                p2 (my-transform (list (car allMax) (cadr allMin) (caddr allMin))) ;; 우하
                p3 (my-transform allMax) ;; 우상
                p4 (my-transform (list (car allMin) (cadr allMax) (caddr allMin)))) ;; 좌상

          (princ "\n--- [추출 결과 (OLE/해치 제외)] ---")
          (princ (strcat "\n1. 좌측 하단: " (vl-prin1-to-string p1)))
          (princ (strcat "\n2. 우측 하단: " (vl-prin1-to-string p2)))
          (princ (strcat "\n3. 우측 상단: " (vl-prin1-to-string p3)))
          (princ (strcat "\n4. 좌측 상단: " (vl-prin1-to-string p4)))
          
          ;; (선택 사항) 제대로 잡혔는지 확인용 사각형 그리기
          ;; (command "_pline" p1 p2 p3 p4 "_c")
        )
        (princ "\n오류: 계산 가능한 일반 객체가 블록 내에 없습니다.")
      )
    )
    (princ "\n블록(INSERT) 객체가 아닙니다.")
  )
  (princ)
)