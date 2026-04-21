;;; ============================================================
;;; BLKSWITCH.LSP  (블럭 길이방향 + 뷰 좌우 기준)
;;; 화면 클릭으로 가장 가까운 블럭을 선택하고
;;; A : 왼쪽으로 늘리기   S : 왼쪽에서 줄이기
;;; D : 오른쪽에서 줄이기  F : 오른쪽으로 늘리기
;;; Z : ←500  X : ←100  C : →100  V : →500
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

(defun BSW:cross (a b)
  (list (- (* (cadr a) (caddr b)) (* (caddr a) (cadr b)))
        (- (* (caddr a) (car b))  (* (car a)  (caddr b)))
        (- (* (car a)  (cadr b))  (* (cadr a) (car b)))))

(defun BSW:normalize (v / len)
  (setq len (sqrt (+ (* (car v) (car v))
                     (* (cadr v) (cadr v))
                     (* (caddr v) (caddr v)))))
  (if (> len 1e-10)
    (list (/ (car v) len) (/ (cadr v) len) (/ (caddr v) len))
    '(1.0 0.0 0.0)))

;;; AABB 8꼭짓점을 dir 에 투영한 최대값
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

;;; AABB 8꼭짓점을 dir 에 투영한 최소값
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
;; 블럭 길이방향 계산
;; ============================================================

;;; 블럭의 로컬 X축 방향을 WCS 로 반환
;;; AutoCAD 임의축 알고리즘(Arbitrary Axis Algorithm) + rotation 적용
(defun BSW:block-local-x (ent / ed normal rot ax ay)
  (setq ed     (entget ent)
        normal (cdr (assoc 210 ed))
        rot    (if (assoc 50 ed) (cdr (assoc 50 ed)) 0.0))
  (if (not normal) (setq normal '(0.0 0.0 1.0)))
  (setq normal (BSW:normalize normal))

  ;; 임의축 알고리즘: OCS X축(ax) 결정
  (if (and (< (abs (car normal)) 0.015625)      ; 1/64
           (< (abs (cadr normal)) 0.015625))
    (setq ax (BSW:normalize (BSW:cross '(0.0 1.0 0.0) normal)))
    (setq ax (BSW:normalize (BSW:cross '(0.0 0.0 1.0) normal))))
  (setq ay (BSW:normalize (BSW:cross normal ax)))

  ;; rotation 적용: local-X = ax*cos(rot) + ay*sin(rot)
  (BSW:normalize
    (BSW:vec+ (BSW:vec* (cos rot) ax)
              (BSW:vec* (sin rot) ay))))

;;; 블럭 길이방향 - 뷰의 오른쪽과 같은 방향으로 정렬해서 반환
;;; (dot < 0 이면 반전 → 항상 "화면 오른쪽에 가까운 쪽"이 양의 방향)
(defun BSW:get-length-dir (ent / lx view-x)
  (setq lx     (BSW:block-local-x ent)
        view-x (trans '(1.0 0.0 0.0) 2 0 T))
  (if (< (BSW:dot lx view-x) 0)
    (BSW:vec* -1.0 lx)
    lx))

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

(defun BSW:get-bbox (ent / obj minpt maxpt)
  (setq obj (vlax-ename->vla-object ent))
  (if (not (vl-catch-all-error-p
             (vl-catch-all-apply 'vla-getboundingbox
                                 (list obj 'minpt 'maxpt))))
    (list (vlax-safearray->list minpt)
          (vlax-safearray->list maxpt))
    nil))

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

;; ============================================================
;; 블럭 교체 + 길이방향 한쪽 끝 고정
;;
;; anchor 'R = 화면 오른쪽 끝 고정 (A/S: 왼쪽 변화)
;; anchor 'L = 화면 왼쪽 끝 고정  (D/F: 오른쪽 변화)
;;
;; 뷰 방향이 아니라 블럭의 실제 길이방향(local-X)을 사용.
;; 단, 두 방향 중 뷰 오른쪽에 더 가까운 쪽을 +방향으로 통일.
;; ============================================================
(defun BSW:switch-anchored (ent new-name anchor
                            / obj ldir omn omx nmn nmx
                              old-mn old-mx new-mn new-mx
                              old-proj new-proj delta ins ins3)
  (setq obj  (vlax-ename->vla-object ent)
        ldir (BSW:get-length-dir ent))   ; 길이방향 (뷰 오른쪽 정렬)

  (vla-getboundingbox obj 'omn 'omx)
  (setq old-mn (vlax-safearray->list omn)
        old-mx (vlax-safearray->list omx))

  (vla-put-name obj new-name)
  (vla-update obj)

  (vla-getboundingbox obj 'nmn 'nmx)
  (setq new-mn (vlax-safearray->list nmn)
        new-mx (vlax-safearray->list nmx))

  ;; 고정 끝을 길이방향 투영으로 결정
  (if (= anchor 'R)
    (setq old-proj (BSW:proj-max old-mn old-mx ldir)
          new-proj (BSW:proj-max new-mn new-mx ldir))
    (setq old-proj (BSW:proj-min old-mn old-mx ldir)
          new-proj (BSW:proj-min new-mn new-mx ldir)))

  ;; 길이방향으로 삽입점 이동
  (setq delta (- old-proj new-proj)
        ins   (cdr (assoc 10 (entget ent)))
        ins3  (list (car ins) (cadr ins) (if (caddr ins) (caddr ins) 0.0)))
  (vla-put-insertionpoint obj
    (vlax-3d-point (BSW:vec+ ins3 (BSW:vec* delta ldir))))
  (vla-update obj))

;;; 블럭 길이방향으로 mm 만큼 이동
(defun BSW:move-block (ent mm / obj ldir ins ins3)
  (setq obj  (vlax-ename->vla-object ent)
        ldir (BSW:get-length-dir ent)
        ins  (cdr (assoc 10 (entget ent)))
        ins3 (list (car ins) (cadr ins) (if (caddr ins) (caddr ins) 0.0)))
  (vla-put-insertionpoint obj
    (vlax-3d-point (BSW:vec+ ins3 (BSW:vec* mm ldir))))
  (vla-update obj))

(defun BSW:print-status (name idx arrow)
  (princ (strcat "\n  " arrow "  " name
                 "  [" (itoa (1+ idx)) "/" (itoa (length *BSW:list*)) "]")))

(defun BSW:do-switch (sel-ent dir anchor arrow / cur-idx new-idx new-name new-bbox)
  (setq cur-idx (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*))
  (cond
    ((= cur-idx -1)  (princ "\n  선택한 블럭이 목록에 없습니다.") nil)
    ((and (= dir  1) (>= cur-idx (1- (length *BSW:list*))))
     (princ "\n  이미 마지막 블럭입니다.") nil)
    ((and (= dir -1) (<= cur-idx 0))
     (princ "\n  이미 첫 번째 블럭입니다.") nil)
    (T
     (setq new-idx (+ cur-idx dir) new-name (nth new-idx *BSW:list*))
     (BSW:switch-anchored sel-ent new-name anchor)
     (redraw)
     (setq new-bbox (BSW:get-bbox sel-ent))
     (BSW:draw-box new-bbox *BSW:color*)
     (BSW:print-status new-name new-idx arrow)
     new-bbox)))

(defun BSW:do-move (sel-ent mm label / new-bbox)
  (BSW:move-block sel-ent mm)
  (redraw)
  (setq new-bbox (BSW:get-bbox sel-ent))
  (BSW:draw-box new-bbox *BSW:color*)
  (princ (strcat "\n  " label "  " (rtos (abs mm) 2 0) "mm"))
  new-bbox)

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

         ;; A : 왼쪽으로 늘리기 (다음 블럭 + 오른쪽 끝 고정)
         ((member grval '(65 97))
          (setq result (BSW:do-switch sel-ent 1 'R "<- 늘리기"))
          (if result (setq cur-bbox result)))

         ;; S : 왼쪽에서 줄이기 (이전 블럭 + 오른쪽 끝 고정)
         ((member grval '(83 115))
          (setq result (BSW:do-switch sel-ent -1 'R "-> 줄이기"))
          (if result (setq cur-bbox result)))

         ;; D : 오른쪽에서 줄이기 (이전 블럭 + 왼쪽 끝 고정)
         ((member grval '(68 100))
          (setq result (BSW:do-switch sel-ent -1 'L "<- 줄이기"))
          (if result (setq cur-bbox result)))

         ;; F : 오른쪽으로 늘리기 (다음 블럭 + 왼쪽 끝 고정)
         ((member grval '(70 102))
          (setq result (BSW:do-switch sel-ent 1 'L "-> 늘리기"))
          (if result (setq cur-bbox result)))

         ;; Z : 길이방향 왼쪽으로 500mm 이동
         ((member grval '(90 122))
          (setq result (BSW:do-move sel-ent -500 "<- 500mm"))
          (if result (setq cur-bbox result)))

         ;; X : 길이방향 왼쪽으로 100mm 이동
         ((member grval '(88 120))
          (setq result (BSW:do-move sel-ent -100 "<- 100mm"))
          (if result (setq cur-bbox result)))

         ;; C : 길이방향 오른쪽으로 100mm 이동
         ((member grval '(67 99))
          (setq result (BSW:do-move sel-ent 100 "-> 100mm"))
          (if result (setq cur-bbox result)))

         ;; V : 길이방향 오른쪽으로 500mm 이동
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
