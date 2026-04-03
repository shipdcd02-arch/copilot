(defun c:BLK_BOUND_ADV (/ ent insPt rot scaleX scaleY scaleZ blkName blkDef 
                          minPt maxPt allMin allMax objMin objMax 
                          p1 p2 p3 p4 mat)
  (vl-load-com)

  ;; 1. 블록 선택
  (setq ent (car (entsel "\n경계를 추출할 블록을 선택하세요: ")))
  
  (if (and ent (= (cdr (assoc 0 (entget ent))) "INSERT"))
    (progn
      (setq obj (vlax-ename->vla-object ent)
            insPt (vlax-safearray->list (vlax-variant-value (vla-get-InsertionPoint obj)))
            rot (vla-get-Rotation obj)
            scaleX (vla-get-ScaleFactor obj)
            scaleY (vla-get-ScaleFactor obj) ;; 일반적인 블록 기준
            blkName (vla-get-Name obj)
            blkDef (vla-item (vla-get-blocks (vla-get-activedocument (vlax-get-acad-object))) blkName)
            allMin nil
            allMax nil)

      ;; 2. 블록 내부 객체 순회 (OLE, HATCH 제외)
      (vlax-for subObj blkDef
        (setq oName (vla-get-ObjectName subObj))
        (if (not (or (wcmatch oName "AcDbOle*") (wcmatch oName "AcDbHatch")))
          (if (not (vl-catch-all-error-p (vl-catch-all-apply 'vla-getboundingbox (list subObj 'objMin 'objMax))))
            (progn
              (setq tmpMin (vlax-safearray->list objMin)
                    tmpMax (vlax-safearray->list objMax))
              
              ;; 전체 최소/최대값 갱신 (블록 내부 좌표계 기준)
              (if (null allMin)
                (setq allMin tmpMin allMax tmpMax)
                (setq allMin (mapcar 'min allMin tmpMin)
                      allMax (mapcar 'max allMax tmpMax))
              )
            )
          )
        )
      )

      ;; 3. 추출된 좌표를 실제 도면 좌표(WCS)로 변환
      (if (and allMin allMax)
        (progn
          ;; 블록 내부 4개 꼭지점 정의
          (setq p1 allMin
                p2 (list (car allMax) (cadr allMin) (caddr allMin))
                p3 allMax
                p4 (list (car allMin) (cadr allMax) (caddr allMin)))

          ;; 좌표 변환 함수 (회전 및 축척 적용)
          (defun transform-pt (pt ins r sx sy / x y nx ny)
            (setq x (* (car pt) sx)
                  y (* (cadr pt) sy))
            (setq nx (+ (- (* x (cos r)) (* y (sin r))) (car ins))
                  ny (+ (+ (* x (sin r)) (* y (cos r))) (cadr ins)))
            (list nx ny (caddr ins))
          )

          ;; 최종 4개 꼭지점 계산
          (setq p1 (transform-pt p1 insPt rot scaleX scaleY)
                p2 (transform-pt p2 insPt rot scaleX scaleY)
                p3 (transform-pt p3 insPt rot scaleX scaleY)
                p4 (transform-pt p4 insPt rot scaleX scaleY))

          ;; 4. 결과 출력
          (princ "\n--- [OLE/Hatch 제외] 실제 좌표 결과 ---")
          (princ (strcat "\n좌하단 (P1): " (vl-prin1-to-string p1)))
          (princ (strcat "\n우하단 (P2): " (vl-prin1-to-string p2)))
          (princ (strcat "\n우상단 (P3): " (vl-prin1-to-string p3)))
          (princ (strcat "\n좌상단 (P4): " (vl-prin1-to-string p4)))
          
          ;; 시각적 확인용 (점 생성)
          (vla-put-Coordinates (vla-addPolyline (vla-get-ModelSpace (vla-get-ActiveDocument (vlax-get-acad-object))) 
            (vlax-make-variant (vlax-safearray-fill (vlax-make-safearray vlax-vbDouble '(0 . 11)) 
            (append p1 p2 p3 p4)))) 1)
        )
        (princ "\n계산 가능한 객체가 블록 내부에 없습니다.")
      )
    )
    (princ "\n선택한 객체가 블록(INSERT)이 아닙니다.")
  )
  (princ)
)