(defun c:CutSolidCenters (/ matList ss i ent layerName matchedMat obj cen pt new-ss basePt)
  (vl-load-com)
  
  ;; 1. 미리 정의할 자재명(블록명) 리스트
  ;; 레이어 이름에 이 텍스트가 포함되어 있는지 검사하고, 이 이름과 동일한 블록을 삽입합니다.
  (setq matList '("C1-1" "C1-2" "C2-1" "C2-2" "추가자재명1" "추가자재명2")) 

  ;; 3D 솔리드 영역 선택
  (princ "\n영역을 드래그하여 3D 솔리드를 선택하세요 (전체 선택 시 'all' 입력): ")
  (if (setq ss (ssget '((0 . "3DSOLID"))))
    (progn
      (setq new-ss (ssadd)) ;; 생성된 블록들을 따로 모아둘 빈 선택셋
      (setq i 0)
      
      ;; 2. 선택된 솔리드들을 하나씩 반복 처리
      (repeat (sslength ss)
        (setq ent (ssname ss i))
        (setq layerName (cdr (assoc 8 (entget ent)))) ;; 솔리드의 레이어 이름 추출
        
        ;; 해당 레이어 이름에 자재명 리스트 중 하나가 포함되어 있는지 검사
        (setq matchedMat nil)
        (foreach mat matList
          ;; 대소문자 구분 없이 레이어 이름에 자재명이 포함되어 있는지 확인
          (if (vl-string-search (strcase mat) (strcase layerName))
            (setq matchedMat mat) ;; 일치하는 자재명을 저장
          )
        )
        
        ;; 3. 일치하는 자재명이 있고, 해당 도면에 그 이름의 블록이 존재할 경우에만 실행
        (if (and matchedMat (tblsearch "BLOCK" matchedMat))
          (progn
            (setq obj (vlax-ename->vla-object ent))
            
            ;; 솔리드의 기하학적 중심(Centroid) 추출
            (setq cen (vlax-safearray->list (vlax-variant-value (vla-get-centroid obj))))
            
            ;; X, Y 좌표는 그대로 두고, Z좌표만 0.0으로 강제 설정
            (setq pt (list (car cen) (cadr cen) 0.0))
            
            ;; 해당 좌표에 자재명과 동일한 이름의 블록 삽입
            (if (entmake (list '(0 . "INSERT") (cons 2 matchedMat) (cons 10 pt)))
              (ssadd (entlast) new-ss) ;; 방금 삽입한 블록을 선택셋에 추가
            )
          )
        )
        (setq i (1+ i))
      )
      
      ;; 4. 생성된 모든 블록을 한 번에 '기준점 잘라내기'
      (if (> (sslength new-ss) 0)
        (progn
          ;; 사용자에게 기준점 클릭 요청
          (if (setq basePt (getpoint "\n잘라내기(클립보드 저장)할 기준점을 클릭하세요: "))
            (progn
              ;; 기준점을 사용하여 클립보드로 복사 (Ctrl+Shift+C 와 동일)
              (command "_.COPYBASE" basePt new-ss "")
              ;; 복사가 완료되면 해당 객체들 즉시 삭제 (잘라내기 효과)
              (command "_.ERASE" new-ss "")
              (princ (strcat "\n▶ 총 " (itoa (sslength new-ss)) "개의 블록이 클립보드로 잘라내기 되었습니다. (대상 도면에 붙여넣기 하세요)"))
            )
            ;; ESC를 누르거나 허공을 클릭해 기준점 지정을 취소한 경우
            (princ "\n▶ 기준점 지정이 취소되어 블록들이 화면에 남았습니다.")
          )
        )
        (princ "\n▶ 생성된 블록이 없습니다. (조건: 솔리드 레이어에 자재명 포함 & 동일 이름 블록 존재)")
      )
    )
    (princ "\n▶ 선택된 3D 솔리드가 없습니다.")
  )
  (princ)
)