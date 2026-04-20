;;; ============================================================
;;; BLKSWITCH.LSP
;;; 화면 클릭으로 가장 가까운 블럭을 선택하고
;;; A 키 : 목록에서 이전 블럭으로 교체
;;; D 키 : 목록에서 다음 블럭으로 교체
;;; ESC  : 종료
;;; ============================================================

(vl-load-com)

;; ★★ 사용할 블럭 목록 - 여기를 수정하세요 ★★
(setq *BSW:list*
  '("BLOCK_A"
    "BLOCK_B"
    "BLOCK_C"
    "BLOCK_D"
    "BLOCK_E"))

;; ============================================================
;; 헬퍼 함수
;; ============================================================

;;; 리스트에서 item의 인덱스 반환 (없으면 -1)
(defun BSW:index-of (item lst / i)
  (setq i 0)
  (while (and lst (not (equal (car lst) item)))
    (setq lst (cdr lst) i (1+ i)))
  (if lst i -1))

;;; 점 pt 주변 윈도우에서 가장 가까운 INSERT 반환 (점점 확장)
(defun BSW:find-nearest (pt / ss i ent ep dist best-ent best-dist r p1 p2)
  (setq best-ent  nil
        best-dist 1e38
        ; 초기 반경: 현재 뷰 높이의 5% (화면 크기에 비례)
        r (max (/ (getvar "VIEWSIZE") 20.0) 1e-6))
  (while (and (not best-ent) (< r 1e15))
    (setq p1 (list (- (car pt) r) (- (cadr pt) r) 0.0)
          p2 (list (+ (car pt) r) (+ (cadr pt) r) 0.0)
          ss (ssget "_C" p1 p2 '((0 . "INSERT"))))
    (if ss
      (progn
        (setq i 0)
        (while (< i (sslength ss))
          (setq ent  (ssname ss i)
                ep   (cdr (assoc 10 (entget ent)))
                dist (distance pt ep))
          (if (< dist best-dist) (setq best-dist dist best-ent ent))
          (setq i (1+ i))))
      (setq r (* r 10)))) ; 없으면 반경 10배 확장
  best-ent)

;;; 블럭의 화면상 바운딩 박스 꼭짓점 4개 반환
;;; 마진은 박스 크기에 비례해 자동 계산
(defun BSW:get-corners (ent / obj minpt maxpt mn mx w h mg)
  (setq obj (vlax-ename->vla-object ent))
  (if (not (vl-catch-all-error-p
             (vl-catch-all-apply 'vla-getboundingbox
                                 (list obj 'minpt 'maxpt))))
    (progn
      (setq mn (vlax-safearray->list minpt)
            mx (vlax-safearray->list maxpt)
            w  (abs (- (car  mx) (car  mn)))
            h  (abs (- (cadr mx) (cadr mn)))
            mg (max (* (max w h) 0.08) 0.5)) ; 박스 크기의 8%, 최소 0.5
      (list
        (list (- (car mn) mg) (- (cadr mn) mg) 0.0) ; 좌하
        (list (+ (car mx) mg) (- (cadr mn) mg) 0.0) ; 우하
        (list (+ (car mx) mg) (+ (cadr mx) mg) 0.0) ; 우상
        (list (- (car mn) mg) (+ (cadr mx) mg) 0.0) ; 좌상
      ))
    nil)) ; 바운딩 박스 계산 실패

;;; XOR 방식으로 사각 테두리 그리기 / 지우기 (같은 색으로 두 번 호출 = 지우기)
(defun BSW:draw-rect (pts color)
  (if pts
    (progn
      (grdraw (nth 0 pts) (nth 1 pts) color 1)
      (grdraw (nth 1 pts) (nth 2 pts) color 1)
      (grdraw (nth 2 pts) (nth 3 pts) color 1)
      (grdraw (nth 3 pts) (nth 0 pts) color 1))))

;;; 블럭 이름 교체 후 업데이트
(defun BSW:set-name (ent new-name / obj)
  (setq obj (vlax-ename->vla-object ent))
  (vla-put-name obj new-name)
  (vla-update   obj))

;;; 상태 메시지 출력 (현재 블럭명과 목록 위치)
(defun BSW:print-status (name idx direction)
  (princ (strcat "\n  " direction " " name
                 "  [" (itoa (1+ idx)) "/"
                 (itoa (length *BSW:list*)) "]")))

;; ============================================================
;; 메인 명령 : BLKSWITCH
;; ============================================================

(defun C:BLKSWITCH ( / sel-ent rect-pts grtype grval cur-idx new-idx new-name done)

  (setq sel-ent  nil
        rect-pts nil
        done     nil)

  (princ "\n┌─────────────────────────────┐")
  (princ "\n│  BLKSWITCH                  │")
  (princ "\n│  클릭 : 가장 가까운 블럭 선택│")
  (princ "\n│  A    : 목록에서 이전 블럭  │")
  (princ "\n│  D    : 목록에서 다음 블럭  │")
  (princ "\n│  ESC  : 종료                │")
  (princ "\n└─────────────────────────────┘")
  (princ (strcat "\n  블럭 목록: "
                 (apply 'strcat
                        (mapcar '(lambda (b) (strcat b "  ")) *BSW:list*))))

  (while (not done)
    (setq grtype (car  (setq _gr (grread T 4 0)))
          grval  (cadr _gr))

    (cond

      ;; ── 마우스 이동 : 무시 ──
      ((= grtype 5) nil)

      ;; ── 마우스 왼쪽 클릭 : 가장 가까운 블럭 선택 ──
      ((= grtype 3)
       (if rect-pts (BSW:draw-rect rect-pts 3)) ; 기존 테두리 XOR-지우기
       (setq rect-pts nil sel-ent nil)

       (setq sel-ent (BSW:find-nearest grval))
       (cond
         ((not sel-ent)
          (princ "\n  근처에 블럭이 없습니다."))

         ((= -1 (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*))
          (princ (strcat "\n  '" (cdr (assoc 2 (entget sel-ent)))
                         "' 은(는) 블럭 목록에 없습니다."))
          (setq sel-ent nil))

         (T
          (setq rect-pts (BSW:get-corners sel-ent))
          (BSW:draw-rect rect-pts 3) ; 초록 테두리 표시
          (BSW:print-status
            (cdr (assoc 2 (entget sel-ent)))
            (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*)
            "선택:"))))

      ;; ── 키보드 입력 ──
      ((= grtype 2)
       (cond

         ;; A 또는 a : 이전 블럭
         ((member grval '(65 97))
          (cond
            ((not sel-ent)
             (princ "\n  먼저 블럭을 클릭으로 선택하세요."))
            (T
             (setq cur-idx (BSW:index-of
                             (cdr (assoc 2 (entget sel-ent))) *BSW:list*))
             (if (= cur-idx -1)
               (princ "\n  선택한 블럭이 목록에 없습니다.")
               (if (<= cur-idx 0)
                 (princ "\n  이미 첫 번째 블럭입니다.")
                 (progn
                   (if rect-pts (BSW:draw-rect rect-pts 3))
                   (setq new-idx  (1- cur-idx)
                         new-name (nth new-idx *BSW:list*))
                   (BSW:set-name sel-ent new-name)
                   (setq rect-pts (BSW:get-corners sel-ent))
                   (BSW:draw-rect rect-pts 3)
                   (BSW:print-status new-name new-idx "←")))))))

         ;; D 또는 d : 다음 블럭
         ((member grval '(68 100))
          (cond
            ((not sel-ent)
             (princ "\n  먼저 블럭을 클릭으로 선택하세요."))
            (T
             (setq cur-idx (BSW:index-of
                             (cdr (assoc 2 (entget sel-ent))) *BSW:list*))
             (if (= cur-idx -1)
               (princ "\n  선택한 블럭이 목록에 없습니다.")
               (if (>= cur-idx (1- (length *BSW:list*)))
                 (princ "\n  이미 마지막 블럭입니다.")
                 (progn
                   (if rect-pts (BSW:draw-rect rect-pts 3))
                   (setq new-idx  (1+ cur-idx)
                         new-name (nth new-idx *BSW:list*))
                   (BSW:set-name sel-ent new-name)
                   (setq rect-pts (BSW:get-corners sel-ent))
                   (BSW:draw-rect rect-pts 3)
                   (BSW:print-status new-name new-idx "→")))))))

         ;; ESC : 종료
         ((= grval 27)
          (if rect-pts (BSW:draw-rect rect-pts 3)) ; 테두리 지우기
          (setq done T)
          (princ "\n  종료되었습니다.\n"))

       )) ; end keyboard cond

    ) ; end main cond
  ) ; end while

  (princ))

;;; BLKSWITCH 로드 확인 메시지
(princ "\nBLKSWITCH 로드 완료 - 명령어: BLKSWITCH")
(princ)
