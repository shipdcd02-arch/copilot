(defun c:CutSolidCenters (/ matList layerFilter ss i ent layerName matchedMat obj cen pt new-ss basePt)
  (vl-load-com)
  
  ;; 1. 미리 정의할 자재명(블록명) 리스트
  (setq matList '("C1-1" "C1-2" "C2-1" "C2-2" "추가자재명1" "추가자재명2")) 

  ;; 2. 선택 필터(Filter) 문자열 자동 생성
  ;; 리스트를 활용해 "*C1-1*,*C1-2*,*C2-1*..." 와 같은 형태의 문자열을 만듭니다.
  (setq layerFilter "")
  (foreach mat matList
    (if (= layerFilter "")
      (setq layerFilter (strcat "*" mat "*"))
      (setq layerFilter (strcat layerFilter ",*" mat "*"))
    )
  )

  ;; 3. 3D 솔리드 & 특정 레이어 영역 선택 (필터 적용)
  (princ "\n영역을 드래그하세요 (자재명이 포함된 레이어의 3D 솔리드만 자동 선택됩니다): ")
  ;; ssget에 필터 리스트 적용: (0 . "3DSOLID") AND (8 . "*C1-1*,*C1-2*...")
  (if (setq ss (ssget (list '(0 . "3DSOLID") (cons 8 layerFilter))))
    (progn
      (setq new-ss (ssadd)) ;; 생성된 블록들을 따로 모아둘 빈 선택셋
      (setq i 0)
      
      ;; 4. 걸러진 솔리드들을 하나씩 반복 처리
      (repeat (sslength ss)
        (setq ent (ssname ss i))
        (setq layerName (cdr (assoc 8 (entget ent))))
        
        ;; 해당 솔리드가 리스트 중 정확히 어떤 자재명과 매칭되는지 확인
        (setq matchedMat nil)
        (foreach mat matList
          (if (vl-string-search (strcase mat) (strcase layerName))
            (setq matchedMat mat)
          )
        )
        
        ;; 일치하는 자재명이 있고, 해당 도면에 그 이름의 블록이 존재할 경우
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
      
      ;; 5. 생성된 모든 블록을 한 번에 '기준점 잘라내기'
      (if (> (sslength new-ss) 0)
        (progn
          (if (setq basePt (getpoint "\n잘라내기(클립보드 저장)할 기준점을 클릭하세요: "))
            (progn
              (command "_.COPYBASE" basePt new-ss "")
              (command "_.ERASE" new-ss "")
              (princ (strcat "\n▶ 총 " (itoa (sslength new-ss)) "개의 블록이 클립보드로 잘라내기 되었습니다. (대상 도면에 붙여넣기 하세요)"))
            )
            (princ "\n▶ 기준점 지정이 취소되어 블록들이 화면에 남았습니다.")
          )
        )
        (princ "\n▶ 생성된 블록이 없습니다. (조건: 동일 이름의 블록이 도면에 정의되어 있어야 함)")
      )
    )
    (princ "\n▶ 선택된 영역에 자재명이 포함된 레이어의 3D 솔리드가 없습니다.")
  )
  (princ)
)