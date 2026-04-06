(defun c:CutSolidCenters (/ ss i ent obj cen pt new-ss basePt radius)
  (vl-load-com)
  
  ;; 1. 3D 솔리드 영역 선택
  (princ "\n영역을 드래그하여 3D 솔리드를 선택하세요: ")
  (if (setq ss (ssget '((0 . "3DSOLID"))))
    (progn
      (setq new-ss (ssadd)) ;; 방금 그린 객체들만 따로 모아둘 빈 선택셋
      (setq radius 100.0)   ;; 그려질 원의 반지름 (도면 스케일에 맞게 숫자를 수정하세요)

      (setq i 0)
      ;; 2. 선택된 솔리드들을 하나씩 반복 처리
      (repeat (sslength ss)
        (setq ent (ssname ss i))
        (setq obj (vlax-ename->vla-object ent))
        
        ;; 솔리드의 기하학적 중심(Centroid) 추출
        (setq cen (vlax-safearray->list (vlax-variant-value (vla-get-centroid obj))))
        
        ;; X, Y 좌표는 그대로 두고, Z좌표만 0.0으로 강제 설정
        (setq pt (list (car cen) (cadr cen) 0.0))
        
        ;; 3. 해당 좌표에 2D 원 그리기
        ;; -------------------------------------------------------------------
        (entmake 
          (list 
            '(0 . "CIRCLE") 
            (cons 10 pt) 
            (cons 40 radius)
          )
        )
        
        ;; [나중에 블록으로 바꿀 때] 위 entmake(원 그리기) 부분을 지우고 아래 코드를 사용하세요.
        ;; "MyBlock" 부분을 실제 삽입할 블록 이름으로 바꾸시면 됩니다.
        ;; (entmake (list '(0 . "INSERT") (cons 2 "MyBlock") (cons 10 pt)))
        ;; -------------------------------------------------------------------
        
        ;; 방금 그린 객체(원 또는 블록)를 선택셋에 추가
        (ssadd (entlast) new-ss)
        (setq i (1+ i))
      )
      
      ;; 4. 생성된 모든 객체를 한 번에 '기준점 잘라내기'
      (if (> (sslength new-ss) 0)
        (progn
          ;; 사용자에게 기준점 클릭 요청
          (if (setq basePt (getpoint "\n잘라내기(클립보드 저장)할 기준점을 클릭하세요: "))
            (progn
              ;; 기준점을 사용하여 클립보드로 복사 (Ctrl+Shift+C 와 동일)
              (command "_.COPYBASE" basePt new-ss "")
              ;; 복사가 완료되면 해당 객체들 즉시 삭제 (잘라내기 효과)
              (command "_.ERASE" new-ss "")
              (princ (strcat "\n" (itoa (sslength new-ss)) "개의 심볼이 클립보드로 잘라내기 되었습니다. (다른 도면에 붙여넣기 하세요)"))
            )
            ;; ESC를 누르거나 허공을 클릭해 기준점 지정을 취소한 경우 (삭제하지 않고 남김)
            (princ "\n기준점 지정이 취소되어 객체가 화면에 남았습니다.")
          )
        )
      )
    )
    (princ "\n선택된 3D 솔리드가 없습니다.")
  )
  (princ)
)