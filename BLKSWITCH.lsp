;;; ============================================================
;;; BLKSWITCH.LSP
;;; 화면 클릭으로 가장 가까운 블럭을 선택하고
;;; A : 왼쪽으로 늘리기   S : 왼쪽에서 줄이기
;;; F : 오른쪽으로 늘리기  D : 오른쪽에서 줄이기
;;; ESC / Space / Enter : 종료
;;; ============================================================

(vl-load-com)

;; ★★ 하이라이트 색상 (1=빨강 2=노랑 3=초록 4=하늘 5=파랑 6=보라 7=흰색) ★★
(setq *BSW:color* 3)

;; ★★ 블럭 목록 - 짧은 것부터 긴 순서로 입력하세요 ★★
(setq *BSW:list*
  '("BLOCK_A"
    "BLOCK_B"
    "BLOCK_C"
    "BLOCK_D"
    "BLOCK_E"))

;; ============================================================
;; 헬퍼 함수
;; ============================================================

(defun BSW:index-of (item lst / i)
  (setq i 0)
  (while (and lst (not (equal (car lst) item)))
    (setq lst (cdr lst) i (1+ i)))
  (if lst i -1))

(defun BSW:find-nearest (pt / ss i ent ep dist best-ent best-dist r p1 p2)
  (setq best-ent  nil
        best-dist 1e38
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
      (setq r (* r 10))))
  best-ent)

(defun BSW:get-corners (ent / obj minpt maxpt mn mx)
  (setq obj (vlax-ename->vla-object ent))
  (if (not (vl-catch-all-error-p
             (vl-catch-all-apply 'vla-getboundingbox
                                 (list obj 'minpt 'maxpt))))
    (progn
      (setq mn (vlax-safearray->list minpt)
            mx (vlax-safearray->list maxpt))
      (list
        (list (car mn) (cadr mn) 0.0)
        (list (car mx) (cadr mn) 0.0)
        (list (car mx) (cadr mx) 0.0)
        (list (car mn) (cadr mx) 0.0)))
    nil))

(defun BSW:draw-rect (pts color)
  (if pts
    (progn
      (grdraw (nth 0 pts) (nth 1 pts) color 1)
      (grdraw (nth 1 pts) (nth 2 pts) color 1)
      (grdraw (nth 2 pts) (nth 3 pts) color 1)
      (grdraw (nth 3 pts) (nth 0 pts) color 1))))

;;; 블럭 교체 + 한쪽 끝 고정
;;; anchor 'L = 왼쪽 고정(오른쪽 변화)  'R = 오른쪽 고정(왼쪽 변화)
(defun BSW:switch-anchored (ent new-name anchor
                            / obj ins ins-z omn omx nmn nmx
                              old-mn old-mx new-mn new-mx delta)
  (setq obj (vlax-ename->vla-object ent))

  ; 교체 전 바운딩 박스
  (vla-getboundingbox obj 'omn 'omx)
  (setq old-mn (vlax-safearray->list omn)
        old-mx (vlax-safearray->list omx))

  ; 블럭 이름 교체
  (vla-put-name obj new-name)
  (vla-update obj)

  ; 교체 후 바운딩 박스 (삽입점 그대로인 상태)
  (vla-getboundingbox obj 'nmn 'nmx)
  (setq new-mn (vlax-safearray->list nmn)
        new-mx (vlax-safearray->list nmx))

  ; 고정 기준에 따라 삽입점 X 이동량 계산
  (setq delta
    (if (= anchor 'R)
      (- (car old-mx) (car new-mx))   ; 오른쪽 끝 고정
      (- (car old-mn) (car new-mn)))) ; 왼쪽 끝 고정

  ; 삽입점 이동
  (setq ins   (cdr (assoc 10 (entget ent)))
        ins-z (if (caddr ins) (caddr ins) 0.0))
  (vla-put-insertionpoint obj
    (vlax-3d-point (list (+ (car ins) delta) (cadr ins) ins-z)))
  (vla-update obj))

(defun BSW:print-status (name idx arrow)
  (princ (strcat "\n  " arrow "  " name
                 "  [" (itoa (1+ idx)) "/" (itoa (length *BSW:list*)) "]")))

;; ============================================================
;; 공통 키 처리 (방향 + 앵커)
;; dir  1 = 다음(길어짐)  -1 = 이전(짧아짐)
;; anchor 'L or 'R
;; ============================================================
(defun BSW:do-switch (sel-ent rect-pts dir anchor arrow
                      / cur-idx new-idx new-name)
  (setq cur-idx (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*))
  (cond
    ((= cur-idx -1)
     (princ "\n  선택한 블럭이 목록에 없습니다.")
     rect-pts) ; rect-pts 변경 없이 반환
    ((and (= dir  1) (>= cur-idx (1- (length *BSW:list*))))
     (princ "\n  이미 마지막 블럭입니다.")
     rect-pts)
    ((and (= dir -1) (<= cur-idx 0))
     (princ "\n  이미 첫 번째 블럭입니다.")
     rect-pts)
    (T
     (setq new-idx  (+ cur-idx dir)
           new-name (nth new-idx *BSW:list*))
     (BSW:switch-anchored sel-ent new-name anchor)
     (redraw)
     (setq rect-pts (BSW:get-corners sel-ent))
     (BSW:draw-rect rect-pts *BSW:color*)
     (BSW:print-status new-name new-idx arrow)
     rect-pts)))

;; ============================================================
;; 메인 명령 : BS
;; ============================================================

(defun C:BS ( / sel-ent rect-pts grtype grval done)

  (setq sel-ent  nil
        rect-pts nil
        done     nil)

  (princ "\n[BS]  클릭:선택  A:왼쪽늘리기  S:왼쪽줄이기  D:오른쪽줄이기  F:오른쪽늘리기  Space/ESC:종료")
  (princ (strcat "\n  목록: "
                 (apply 'strcat (mapcar '(lambda (b) (strcat b "  ")) *BSW:list*))))

  (while (not done)
    (setq grtype (car  (setq _gr (grread T 4 0)))
          grval  (cadr _gr))

    (cond

      ((= grtype 5) nil) ; 마우스 이동 무시

      ;; 마우스 클릭
      ((= grtype 3)
       (redraw)
       (setq rect-pts nil sel-ent nil)
       (setq sel-ent (BSW:find-nearest grval))
       (cond
         ((not sel-ent)
          (princ "\n  근처에 블럭이 없습니다."))
         ((= -1 (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*))
          (princ (strcat "\n  '" (cdr (assoc 2 (entget sel-ent))) "' 은(는) 목록에 없습니다."))
          (setq sel-ent nil))
         (T
          (setq rect-pts (BSW:get-corners sel-ent))
          (BSW:draw-rect rect-pts *BSW:color*)
          (BSW:print-status
            (cdr (assoc 2 (entget sel-ent)))
            (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*)
            "선택:"))))

      ;; 키보드
      ((= grtype 2)
       (cond
         ((not sel-ent)
          (if (not (member grval '(27 32 13)))
            (princ "\n  먼저 블럭을 클릭으로 선택하세요.")))

         ;; A : 왼쪽 늘리기 (다음 블럭 + 오른쪽 고정)
         ((member grval '(65 97))
          (setq rect-pts (BSW:do-switch sel-ent rect-pts 1 'R "<- 늘리기")))

         ;; S : 왼쪽 줄이기 (이전 블럭 + 오른쪽 고정)
         ((member grval '(83 115))
          (setq rect-pts (BSW:do-switch sel-ent rect-pts -1 'R "-> 줄이기")))

         ;; D : 오른쪽 줄이기 (이전 블럭 + 왼쪽 고정)
         ((member grval '(68 100))
          (setq rect-pts (BSW:do-switch sel-ent rect-pts -1 'L "<- 줄이기")))

         ;; F : 오른쪽 늘리기 (다음 블럭 + 왼쪽 고정)
         ((member grval '(70 102))
          (setq rect-pts (BSW:do-switch sel-ent rect-pts 1 'L "-> 늘리기")))

         ;; ESC / Space / Enter : 종료
         ((member grval '(27 32 13))
          (redraw)
          (setq done T)
          (princ "\n  종료.\n"))
       ))

    ) ; end cond
  ) ; end while

  (princ))

(princ "\nBLKSWITCH 로드 완료 - 명령어: BS")
(princ)
