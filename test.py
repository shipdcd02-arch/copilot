(defun c:GEN2D (/ ss)
  (setq ss (ssget ":S" '((0 . "SECTIONPLANE")))) ; 단면 평면 객체 하나 선택
  
  (if ss
    (progn
      ;; 명령행 버전으로 단면 블록 생성
      ;; 옵션 순서: 객체 선택 -> 2D -> 파일저장(N) -> 삽입점(0,0) -> 스케일(1) -> 회전(0)
      (command "-SECTIONPLANETOBLOCK" (ssname ss 0) "2" "N" "0,0,0" "1" "1" "0")
      (princ "\n단면이 2D 블록으로 추출되어 (0,0,0) 위치에 삽입되었습니다.")
    )
    (princ "\n단면 평면을 찾을 수 없습니다.")
  )
  (princ)
)