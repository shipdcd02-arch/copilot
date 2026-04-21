;;; ============================================================
;;; BLKSWITCH.LSP  (뷰 방향 기준 3D 대응)
;;; 화면 클릭으로 가장 가까운 블럭을 선택하고
;;; A : 화면 왼쪽으로 늘리기   S : 화면 왼쪽에서 줄이기
;;; D : 화면 오른쪽에서 줄이기  F : 화면 오른쪽으로 늘리기
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
;; 벡터 유틸
;; ============================================================

(defun BSW:dot (a b)
  (+ (* (car a) (car b))
     (* (cadr a) (cadr b))
     (* (caddr a) (caddr b))))

(defun BSW:vec+ (a b)
  (list (+ (car a) (car b))
        (+ (cadr a) (cadr b))
        (+ (caddr a) (caddr b))))

(defun BSW:vec* (s v)
  (list (* s (car v)) (* s (cadr v)) (* s (caddr v))))

;;; AABB(축정렬박스)의 8개 꼭짓점 중 dir 방향 투영 최대값
(defun BSW:proj-max (mn mx dir)
  (apply 'max
    (mapcar (function (lambda (p) (BSW:dot dir p)))
      (list (list (car mn) (cadr mn) (caddr mn))
            (list (car mx) (cadr mn) (caddr mn))
            (list (car mn) (cadr mx) (caddr mn))
            (list (car mx) (cadr mx) (caddr mn))
            (list (car mn) (cadr mn) (caddr mx))
            (list (car mx) (cadr mn) (caddr mx))
            (list (car mn) (cadr mx) (caddr mx))
            (list (car mx) (cadr mx) (caddr mx))))))

;;; AABB 8개 꼭짓점 중 dir 방향 투영 최소값
(defun BSW:proj-min (mn mx dir)
  (apply 'min
    (mapcar (function (lambda (p) (BSW:dot dir p)))
      (list (list (car mn) (cadr mn) (caddr mn))
            (list (car mx) (cadr mn) (caddr mn))
            (list (car mn) (cadr mx) (caddr mn))
            (list (car mx) (cadr mx) (caddr mn))
            (list (car mn) (cadr mn) (caddr mx))
            (list (car mx) (cadr mn) (caddr mx))
            (list (car mn) (cadr mx) (caddr mx))
            (list (car mx) (cadr mx) (caddr mx))))))

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
    (setq p1 (list (- (car pt) r) (- (cadr pt) r))
          p2 (list (+ (car pt) r) (+ (cadr pt) r))
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

;;; 바운딩 박스 반환: (list mn mx)  mn/mx = (x y z)
(defun BSW:get-bbox (ent / obj minpt maxpt)
  (setq obj (vlax-ename->vla-object ent))
  (if (not (vl-catch-all-error-p
             (vl-catch-all-apply 'vla-getboundingbox
                                 (list obj 'minpt 'maxpt))))
    (list (vlax-safearray->list minpt)
          (vlax-safearray->list maxpt))
    nil))

;;; 직육면체 12개 엣지 grdraw XOR
(defun BSW:draw-box (bbox color / mn mx p1 p2 p3 p4 p5 p6 p7 p8)
  (if bbox
    (progn
      (setq mn (car bbox) mx (cadr bbox)
            p1 (list (car mn) (cadr mn) (caddr mn))
            p2 (list (car mx) (cadr mn) (caddr mn))
            p3 (list (car mx) (cadr mx) (caddr mn))
            p4 (list (car mn) (cadr mx) (caddr mn))
            p5 (list (car mn) (cadr mn) (caddr mx))
            p6 (list (car mx) (cadr mn) (caddr mx))
            p7 (list (car mx) (cadr mx) (caddr mx))
            p8 (list (car mn) (cadr mx) (caddr mx)))
      (grdraw p1 p2 color 1) (grdraw p2 p3 color 1)
      (grdraw p3 p4 color 1) (grdraw p4 p1 color 1)
      (grdraw p5 p6 color 1) (grdraw p6 p7 color 1)
      (grdraw p7 p8 color 1) (grdraw p8 p5 color 1)
      (grdraw p1 p5 color 1) (grdraw p2 p6 color 1)
      (grdraw p3 p7 color 1) (grdraw p4 p8 color 1))))

;;; ============================================================
;;; 블럭 교체 + 뷰 기준 한쪽 끝 고정
;;;
;;; anchor 'R = 화면 오른쪽 끝 고정 (A/S 키: 왼쪽 변화)
;;; anchor 'L = 화면 왼쪽 끝 고정  (D/F 키: 오른쪽 변화)
;;;
;;; 원리:
;;;   1) 현재 뷰의 오른쪽 방향벡터(view-x) = DCS X축을 WCS로 변환
;;;   2) bbox 8꼭짓점을 view-x 에 투영 → 화면 기준 오른쪽/왼쪽 끝 위치 파악
;;;   3) 블럭 교체 후 같은 투영 계산
;;;   4) 고정 끝의 투영값 차이(delta)만큼 삽입점을 view-x 방향으로 이동
;;; ============================================================
(defun BSW:switch-anchored (ent new-name anchor
                            / obj view-x
                              omn omx nmn nmx
                              old-mn old-mx new-mn new-mx
                              old-proj new-proj delta ins ins3)
  (setq obj (vlax-ename->vla-object ent))

  ;; 현재 뷰의 화면 오른쪽 방향 (DCS X → WCS 변환)
  (setq view-x (trans '(1.0 0.0 0.0) 2 0 T))

  ;; 교체 전 bbox
  (vla-getboundingbox obj 'omn 'omx)
  (setq old-mn (vlax-safearray->list omn)
        old-mx (vlax-safearray->list omx))

  ;; 블럭 이름 교체
  (vla-put-name obj new-name)
  (vla-update obj)

  ;; 교체 후 bbox (삽입점은 아직 원래 위치)
  (vla-getboundingbox obj 'nmn 'nmx)
  (setq new-mn (vlax-safearray->list nmn)
        new-mx (vlax-safearray->list nmx))

  ;; 고정 끝 투영값 계산
  (if (= anchor 'R)
    (setq old-proj (BSW:proj-max old-mn old-mx view-x)  ; 화면 오른쪽 끝
          new-proj (BSW:proj-max new-mn new-mx view-x))
    (setq old-proj (BSW:proj-min old-mn old-mx view-x)  ; 화면 왼쪽 끝
          new-proj (BSW:proj-min new-mn new-mx view-x)))

  ;; view-x 방향으로 (old-proj - new-proj) 만큼 삽입점 이동
  (setq delta (- old-proj new-proj)
        ins   (cdr (assoc 10 (entget ent)))
        ins3  (list (car ins) (cadr ins) (if (caddr ins) (caddr ins) 0.0)))
  (vla-put-insertionpoint obj
    (vlax-3d-point (BSW:vec+ ins3 (BSW:vec* delta view-x))))
  (vla-update obj))

;;; 블럭 위치 이동 (화면 기준 오른쪽 방향 = 양수, 왼쪽 = 음수)
(defun BSW:move-block (ent mm / obj ins ins3 view-x)
  (setq obj    (vlax-ename->vla-object ent)
        view-x (trans '(1.0 0.0 0.0) 2 0 T)
        ins    (cdr (assoc 10 (entget ent)))
        ins3   (list (car ins) (cadr ins) (if (caddr ins) (caddr ins) 0.0)))
  (vla-put-insertionpoint obj
    (vlax-3d-point (BSW:vec+ ins3 (BSW:vec* mm view-x))))
  (vla-update obj))

(defun BSW:do-move (sel-ent mm label / new-bbox)
  (BSW:move-block sel-ent mm)
  (redraw)
  (setq new-bbox (BSW:get-bbox sel-ent))
  (BSW:draw-box new-bbox *BSW:color*)
  (princ (strcat "\n  " label "  " (rtos (abs mm) 2 0) "mm"))
  new-bbox)

(defun BSW:print-status (name idx arrow)
  (princ (strcat "\n  " arrow "  " name
                 "  [" (itoa (1+ idx)) "/" (itoa (length *BSW:list*)) "]")))

(defun BSW:do-switch (sel-ent dir anchor arrow / cur-idx new-idx new-name new-bbox)
  (setq cur-idx (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*))
  (cond
    ((= cur-idx -1)
     (princ "\n  선택한 블럭이 목록에 없습니다.") nil)
    ((and (= dir  1) (>= cur-idx (1- (length *BSW:list*))))
     (princ "\n  이미 마지막 블럭입니다.") nil)
    ((and (= dir -1) (<= cur-idx 0))
     (princ "\n  이미 첫 번째 블럭입니다.") nil)
    (T
     (setq new-idx  (+ cur-idx dir)
           new-name (nth new-idx *BSW:list*))
     (BSW:switch-anchored sel-ent new-name anchor)
     (redraw)
     (setq new-bbox (BSW:get-bbox sel-ent))
     (BSW:draw-box new-bbox *BSW:color*)
     (BSW:print-status new-name new-idx arrow)
     new-bbox)))

;; ============================================================
;; 메인 명령 : BS
;; ============================================================

(defun C:BS ( / sel-ent cur-bbox grtype grval done result)

  (setq sel-ent  nil
        cur-bbox nil
        done     nil)

  (princ "\n[BS]  클릭:선택  A:왼늘  S:왼줄  D:오줄  F:오늘  Z:←500  X:←100  C:→100  V:→500  Space/ESC:종료")
  (princ (strcat "\n  목록: "
                 (apply 'strcat (mapcar '(lambda (b) (strcat b "  ")) *BSW:list*))))

  (while (not done)
    (setq grtype (car  (setq _gr (grread T 4 0)))
          grval  (cadr _gr))

    (cond

      ((= grtype 5) nil)

      ;; 마우스 클릭
      ((= grtype 3)
       (redraw)
       (setq cur-bbox nil sel-ent nil)
       (setq sel-ent (BSW:find-nearest grval))
       (cond
         ((not sel-ent)
          (princ "\n  근처에 블럭이 없습니다."))
         ((= -1 (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*))
          (princ (strcat "\n  '" (cdr (assoc 2 (entget sel-ent))) "' 은(는) 목록에 없습니다."))
          (setq sel-ent nil))
         (T
          (setq cur-bbox (BSW:get-bbox sel-ent))
          (BSW:draw-box cur-bbox *BSW:color*)
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

         ;; A : 화면 왼쪽으로 늘리기 (다음 블럭 + 화면 오른쪽 끝 고정)
         ((member grval '(65 97))
          (setq result (BSW:do-switch sel-ent 1 'R "<- 늘리기"))
          (if result (setq cur-bbox result)))

         ;; S : 화면 왼쪽에서 줄이기 (이전 블럭 + 화면 오른쪽 끝 고정)
         ((member grval '(83 115))
          (setq result (BSW:do-switch sel-ent -1 'R "-> 줄이기"))
          (if result (setq cur-bbox result)))

         ;; D : 화면 오른쪽에서 줄이기 (이전 블럭 + 화면 왼쪽 끝 고정)
         ((member grval '(68 100))
          (setq result (BSW:do-switch sel-ent -1 'L "<- 줄이기"))
          (if result (setq cur-bbox result)))

         ;; F : 화면 오른쪽으로 늘리기 (다음 블럭 + 화면 왼쪽 끝 고정)
         ((member grval '(70 102))
          (setq result (BSW:do-switch sel-ent 1 'L "-> 늘리기"))
          (if result (setq cur-bbox result)))

         ;; Z : 화면 왼쪽으로 500mm 이동
         ((member grval '(90 122))
          (setq result (BSW:do-move sel-ent -500 "<- 500mm"))
          (if result (setq cur-bbox result)))

         ;; X : 화면 왼쪽으로 100mm 이동
         ((member grval '(88 120))
          (setq result (BSW:do-move sel-ent -100 "<- 100mm"))
          (if result (setq cur-bbox result)))

         ;; C : 화면 오른쪽으로 100mm 이동
         ((member grval '(67 99))
          (setq result (BSW:do-move sel-ent 100 "-> 100mm"))
          (if result (setq cur-bbox result)))

         ;; V : 화면 오른쪽으로 500mm 이동
         ((member grval '(86 118))
          (setq result (BSW:do-move sel-ent 500 "-> 500mm"))
          (if result (setq cur-bbox result)))

         ;; ESC / Space / Enter : 종료
         ((member grval '(27 32 13))
          (redraw)
          (setq done T)
          (princ "\n  종료.\n"))
       ))

    )
  )
  (princ))

(princ "\nBLKSWITCH 로드 완료 - 명령어: BS")
(princ)
