(defun c:BLK_BOUND_FIX (/ ent minpt maxpt p1 p2 p3 p4)
  (setq ent (car (entsel "\n블록을 선택하세요: ")))
  (if ent
    (progn
      ;; 1. 현재 도면의 임시 변수 저장 및 화면 업데이트
      ;; vla-getboundingbox 대신 객체의 bounding box를 직접 계산하는 함수가 없으므로 
      ;; 선택한 객체만 남기고 나머지를 무시하는 방식으로 크기를 추출합니다.
      
      (command "._zoom" "_object" ent "")
      
      ;; 2. 선택한 객체의 좌표 정보를 시스템 변수에서 가져오기
      ;; (주의: 이 방법은 화면에 보이는 범위를 기준으로 하므로 가장 정확합니다)
      (setq minpt (getvar "extmin")
            maxpt (getvar "extmax"))

      (setq p1 (list (car minpt) (cadr minpt))
            p2 (list (car maxpt) (cadr minpt))
            p3 (list (car maxpt) (cadr maxpt))
            p4 (list (car minpt) (cadr maxpt)))

      (princ "\n--- 좌표 추출 결과 ---")
      (princ (format-pt-list (list p1 p2 p3 p4)))
    )
  )
  (princ)
)

(defun format-pt-list (lst)
  (foreach pt lst (princ (strcat "\n좌표: " (vl-prin1-to-string pt))))
  (princ)
)