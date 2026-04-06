(defun c:AutoMakeBlocks (/ oldOsnap oldCmd oldColor oldHpname ss)
  (vl-load-com)
  
  ;; 1. 기존 시스템 변수 백업
  (setq oldOsnap (getvar "OSMODE")
        oldCmd   (getvar "CMDECHO")
        oldColor (getvar "CECOLOR")
        oldHpname (getvar "HPNAME"))

  ;; 2. 작업용 시스템 변수 세팅 (오스냅 끔, 화면출력 끔, 현재색상 파란색, 해치패턴 솔리드)
  (setvar "OSMODE" 0)
  (setvar "CMDECHO" 0)
  (setvar "CECOLOR" "5")       ;; 색상코드 5 = 파란색(Blue)
  (setvar "HPNAME" "SOLID")    ;; 해치 패턴을 단색(Solid)으로 강제 설정

  ;; -----------------------------------------------------------
  ;; [블럭 1] C1-1 : 지름 300 (반지름 150) 파란색 원
  ;; -----------------------------------------------------------
  (if (not (tblsearch "BLOCK" "C1-1"))
    (progn
      (command "_.CIRCLE" '(0 0 0) 150)
      (command "_.-BLOCK" "C1-1" '(0 0 0) (entlast) "")
      (princ "\n▶ [C1-1] 블럭 생성 완료.")
    )
    (princ "\n▶ [C1-1] 블럭은 이미 존재하여 건너뜁니다.")
  )

  ;; -----------------------------------------------------------
  ;; [블럭 2] C1-2 : 지름 300 파란색 원 + 내부 파란색 솔리드 해치
  ;; -----------------------------------------------------------
  (if (not (tblsearch "BLOCK" "C1-2"))
    (progn
      (setq ss (ssadd))
      (command "_.CIRCLE" '(0 0 0) 150)
      (ssadd (entlast) ss)
      (command "_.-HATCH" "_S" (entlast) "" "") ;; 솔리드 해치 삽입
      (ssadd (entlast) ss)
      (command "_.-BLOCK" "C1-2" '(0 0 0) ss "")
      (princ "\n▶ [C1-2] 블럭 생성 완료.")
    )
    (princ "\n▶ [C1-2] 블럭은 이미 존재하여 건너뜁니다.")
  )

  ;; -----------------------------------------------------------
  ;; [블럭 3] C2-1 : 한 변의 길이가 259.8076인 파란색 정삼각형
  ;; (반지름 150인 원에 내접하는 정삼각형의 한 변 길이가 259.8076임)
  ;; -----------------------------------------------------------
  (if (not (tblsearch "BLOCK" "C2-1"))
    (progn
      ;; 중심이 0,0이고 (0,150) 방향으로 꼭짓점이 향하는 내접(_I) 다각형 생성
      (command "_.POLYGON" 3 '(0 0 0) "_I" '(0 150 0))
      (command "_.-BLOCK" "C2-1" '(0 0 0) (entlast) "")
      (princ "\n▶ [C2-1] 블럭 생성 완료.")
    )
    (princ "\n▶ [C2-1] 블럭은 이미 존재하여 건너뜁니다.")
  )

  ;; -----------------------------------------------------------
  ;; [블럭 4] C2-2 : 정삼각형 + 내부 파란색 솔리드 해치
  ;; -----------------------------------------------------------
  (if (not (tblsearch "BLOCK" "C2-2"))
    (progn
      (setq ss (ssadd))
      (command "_.POLYGON" 3 '(0 0 0) "_I" '(0 150 0))
      (ssadd (entlast) ss)
      (command "_.-HATCH" "_S" (entlast) "" "")
      (ssadd (entlast) ss)
      (command "_.-BLOCK" "C2-2" '(0 0 0) ss "")
      (princ "\n▶ [C2-2] 블럭 생성 완료.")
    )
    (princ "\n▶ [C2-2] 블럭은 이미 존재하여 건너뜁니다.")
  )

  ;; 3. 원래 시스템 변수로 복구
  (setvar "OSMODE" oldOsnap)
  (setvar "CMDECHO" oldCmd)
  (setvar "CECOLOR" oldColor)
  (setvar "HPNAME" oldHpname)

  (princ "\n\n*** 모든 블럭 자동 생성 작업이 완료되었습니다 ***")
  (princ)
)