;;; ============================================================
;;; BLKSWITCH.LSP  (OBB 하이라이트 + 블럭 길이방향 + 뷰 좌우 기준)
;;; A:왼늘  S:왼줄  D:오줄  F:오늘
;;; Z:←500  X:←100  C:→100  V:→500
;;; Space / ESC / Enter : 종료
;;; ============================================================

(vl-load-com)

;; ★★ 하이라이트 색상 (1=빨강 2=노랑 3=초록 4=하늘 5=파랑 6=보라 7=흰색) ★★
(setq *BSW:color* 1)

;; ★★ 블럭 목록 - 짧은 것부터 긴 순서로 입력하세요 ★★
(setq *BSW:list*
  '("1M"
    "1.5M"
    "2M"
    "2.5M"
    "3M"))

;; ============================================================
;; 벡터 유틸
;; ============================================================
(defun BSW:dot (a b)
  (+ (* (car a)(car b)) (* (cadr a)(cadr b)) (* (caddr a)(caddr b))))
(defun BSW:vec+ (a b)
  (list (+ (car a)(car b)) (+ (cadr a)(cadr b)) (+ (caddr a)(caddr b))))
(defun BSW:vec* (s v)
  (list (* s (car v)) (* s (cadr v)) (* s (caddr v))))
(defun BSW:cross (a b)
  (list (- (* (cadr a)(caddr b)) (* (caddr a)(cadr b)))
        (- (* (caddr a)(car b))  (* (car a)(caddr b)))
        (- (* (car a)(cadr b))   (* (cadr a)(car b)))))
(defun BSW:normalize (v / len)
  (setq len (sqrt (+ (* (car v)(car v)) (* (cadr v)(cadr v)) (* (caddr v)(caddr v)))))
  (if (> len 1e-10) (list (/ (car v) len) (/ (cadr v) len) (/ (caddr v) len))
    '(1.0 0.0 0.0)))

;; ============================================================
;; 블럭 로컬 축 계산 (임의축 알고리즘 + rotation)
;; ============================================================

;;; 블럭의 OCS 축을 계산해 (lx ly lz) 리스트로 반환
(defun BSW:local-axes (ent / ed normal rot ax ay)
  (setq ed     (entget ent)
        normal (BSW:normalize (if (assoc 210 ed) (cdr (assoc 210 ed)) '(0.0 0.0 1.0)))
        rot    (if (assoc 50 ed) (cdr (assoc 50 ed)) 0.0))
  (if (and (< (abs (car normal)) 0.015625) (< (abs (cadr normal)) 0.015625))
    (setq ax (BSW:normalize (BSW:cross '(0.0 1.0 0.0) normal)))
    (setq ax (BSW:normalize (BSW:cross '(0.0 0.0 1.0) normal))))
  (setq ay (BSW:normalize (BSW:cross normal ax)))
  (list
    (BSW:vec+ (BSW:vec* (cos rot) ax) (BSW:vec* (sin rot) ay))  ; lx
    (BSW:vec+ (BSW:vec* (- (sin rot)) ax) (BSW:vec* (cos rot) ay)) ; ly
    normal))                                                         ; lz

;;; 블럭 길이방향 - 뷰 오른쪽과 같은 방향으로 정렬해 반환
(defun BSW:get-length-dir (ent / lx view-x)
  (setq lx     (car (BSW:local-axes ent))
        view-x (trans '(1.0 0.0 0.0) 2 0 T))
  (if (< (BSW:dot lx view-x) 0) (BSW:vec* -1.0 lx) lx))

;; ============================================================
;; OBB (Oriented Bounding Box) 계산
;;
;; 원리:
;;   1) 블럭을 임시로 ins=(0,0,0) rot=0 normal=(0,0,1) 으로 entmod
;;      → bbox = 블럭 정의 좌표계에서의 실제 extents (= "로컬 좌표")
;;   2) entmod 로 원상복구 (화면 갱신 없음)
;;   3) 실제 local 축 (lx, ly, lz) 으로 8개 꼭짓점을 WCS 변환
;;      → 회전에 딱 맞는 직육면체 꼭짓점 8개
;; ============================================================
(defun BSW:get-obb (ent / ed ed-tmp ins3 normal rot
                         axes lx ly lz
                         obj mn-sa mx-sa mn mx
                         corners cx cy cz)
  (setq ed     (entget ent)
        obj    (vlax-ename->vla-object ent)
        normal (if (assoc 210 ed) (cdr (assoc 210 ed)) '(0.0 0.0 1.0))
        rot    (if (assoc 50  ed) (cdr (assoc 50  ed)) 0.0))

  ;; 임시 상태: ins=(0,0,0) rot=0 normal=(0,0,1)  ← 로컬 bbox 추출용
  (setq ed-tmp ed
        ed-tmp (subst '(10 0.0 0.0 0.0) (assoc 10 ed-tmp) ed-tmp)
        ed-tmp (if (assoc 50 ed-tmp)
                 (subst (cons 50 0.0) (assoc 50 ed-tmp) ed-tmp)
                 (append ed-tmp (list (cons 50 0.0))))
        ed-tmp (if (assoc 210 ed-tmp)
                 (subst '(210 0.0 0.0 1.0) (assoc 210 ed-tmp) ed-tmp)
                 (append ed-tmp (list '(210 0.0 0.0 1.0)))))
  (entmod ed-tmp)   ; 화면 갱신 없이 데이터만 변경

  ;; 로컬 bbox 획득
  (if (not (vl-catch-all-error-p
             (vl-catch-all-apply 'vla-getboundingbox (list obj 'mn-sa 'mx-sa))))
    (setq mn (vlax-safearray->list mn-sa) mx (vlax-safearray->list mx-sa))
    (setq mn '(-0.5 -0.5 -0.5) mx '(0.5 0.5 0.5)))

  ;; 원상복구 (화면 갱신 없음)
  (entmod ed)

  ;; WCS 삽입점: 엔티티 OCS → WCS 변환 (trans + 엔티티명)
  (setq ins3 (trans (cdr (assoc 10 ed)) ent 0))

  ;; 실제 local 축
  (setq axes (BSW:local-axes ent)
        lx (nth 0 axes) ly (nth 1 axes) lz (nth 2 axes))

  ;; 8개 OBB 꼭짓점 WCS 변환
  ;; 순서: cx ∈ {mn,mx} × cy ∈ {mn,mx} × cz ∈ {mn,mx}
  (setq corners nil)
  (foreach cx (list (car mn) (car mx))
    (foreach cy (list (cadr mn) (cadr mx))
      (foreach cz (list (caddr mn) (caddr mx))
        (setq corners (cons
          (BSW:vec+ ins3
            (BSW:vec+ (BSW:vec* cx lx)
              (BSW:vec+ (BSW:vec* cy ly) (BSW:vec* cz lz))))
          corners)))))
  (reverse corners))
;; 인덱스 → 로컬 좌표 대응:
;;  0:(mn,mn,mn) 1:(mn,mn,mx) 2:(mn,mx,mn) 3:(mn,mx,mx)
;;  4:(mx,mn,mn) 5:(mx,mn,mx) 6:(mx,mx,mn) 7:(mx,mx,mx)

;;; OBB 12개 엣지 그리기 (XOR)
(defun BSW:draw-obb (corners color / p0 p1 p2 p3 p4 p5 p6 p7)
  (if corners
    (progn
      (setq p0 (nth 0 corners) p1 (nth 1 corners)
            p2 (nth 2 corners) p3 (nth 3 corners)
            p4 (nth 4 corners) p5 (nth 5 corners)
            p6 (nth 6 corners) p7 (nth 7 corners))
      ;; 아랫면 (cz=mn)
      (grdraw p0 p4 color 1) (grdraw p4 p6 color 1)
      (grdraw p6 p2 color 1) (grdraw p2 p0 color 1)
      ;; 윗면 (cz=mx)
      (grdraw p1 p5 color 1) (grdraw p5 p7 color 1)
      (grdraw p7 p3 color 1) (grdraw p3 p1 color 1)
      ;; 수직 엣지
      (grdraw p0 p1 color 1) (grdraw p4 p5 color 1)
      (grdraw p6 p7 color 1) (grdraw p2 p3 color 1))))

;;; 꼭짓점 리스트를 dir 에 투영한 최대/최소
(defun BSW:proj-max (corners dir)
  (apply 'max (mapcar (function (lambda (p) (BSW:dot dir p))) corners)))
(defun BSW:proj-min (corners dir)
  (apply 'min (mapcar (function (lambda (p) (BSW:dot dir p))) corners)))

;; ============================================================
;; 기타 헬퍼
;; ============================================================
(defun BSW:index-of (item lst / i)
  (setq i 0)
  (while (and lst (not (equal (car lst) item)))
    (setq lst (cdr lst) i (1+ i)))
  (if lst i -1))

(defun BSW:find-nearest (pt / ss i ent ep dist best-ent best-dist r p1 p2)
  (setq best-ent nil best-dist 1e38
        r (max (/ (getvar "VIEWSIZE") 20.0) 1e-6))
  (while (and (not best-ent) (< r 1e15))
    (setq p1 (list (- (car pt) r) (- (cadr pt) r))
          p2 (list (+ (car pt) r) (+ (cadr pt) r))
          ss (ssget "_C" p1 p2 '((0 . "INSERT"))))
    (if ss
      (progn (setq i 0)
        (while (< i (sslength ss))
          (setq ent  (ssname ss i)
                ep   (trans (cdr (assoc 10 (entget ent))) ent 0) ; OCS → WCS
                dist (distance pt ep))
          (if (< dist best-dist) (setq best-dist dist best-ent ent))
          (setq i (1+ i))))
      (setq r (* r 10))))
  best-ent)

;; ============================================================
;; 블럭 교체 + 길이방향 한쪽 끝 고정 (OBB 기반)
;; anchor 'R = 화면 오른쪽 끝 고정  'L = 화면 왼쪽 끝 고정
;; ============================================================
(defun BSW:switch-anchored (ent new-name anchor
                            / obj ldir old-obb new-obb
                              old-proj new-proj delta ins ins3)
  (setq obj   (vlax-ename->vla-object ent)
        ldir  (BSW:get-length-dir ent)
        old-obb (BSW:get-obb ent))

  (vla-put-name obj new-name)
  (vla-update obj)

  (setq new-obb (BSW:get-obb ent))

  (if (= anchor 'R)
    (setq old-proj (BSW:proj-max old-obb ldir)
          new-proj (BSW:proj-max new-obb ldir))
    (setq old-proj (BSW:proj-min old-obb ldir)
          new-proj (BSW:proj-min new-obb ldir)))

  (setq delta (- old-proj new-proj)
        ins3  (trans (cdr (assoc 10 (entget ent))) ent 0)) ; OCS → WCS
  (vla-put-insertionpoint obj (vlax-3d-point (BSW:vec+ ins3 (BSW:vec* delta ldir))))
  (vla-update obj))

;;; 블럭 길이방향으로 mm 이동
(defun BSW:move-block (ent mm / obj ldir ins3)
  (setq obj  (vlax-ename->vla-object ent)
        ldir (BSW:get-length-dir ent)
        ins3 (trans (cdr (assoc 10 (entget ent))) ent 0)) ; OCS → WCS
  (vla-put-insertionpoint obj (vlax-3d-point (BSW:vec+ ins3 (BSW:vec* mm ldir))))
  (vla-update obj))

;;; 화면 위/아래 방향으로 mm 이동 (뷰 기준 Y축)
(defun BSW:move-updown (ent mm / obj view-y ins3)
  (setq obj    (vlax-ename->vla-object ent)
        view-y (trans '(0.0 1.0 0.0) 2 0 T)   ; DCS Y → WCS (화면 위 방향)
        ins3   (trans (cdr (assoc 10 (entget ent))) ent 0))
  (vla-put-insertionpoint obj (vlax-3d-point (BSW:vec+ ins3 (BSW:vec* mm view-y))))
  (vla-update obj))

;;; 블럭 회전 (도 단위 / 양수=반시계 / 음수=시계)
;;; AutoCAD rotation = 블럭 normal 축 기준 CCW 각도 (라디안)
(defun BSW:rotate-block (ent deg / obj cur-rot)
  (setq obj     (vlax-ename->vla-object ent)
        cur-rot (if (assoc 50 (entget ent))
                  (cdr (assoc 50 (entget ent))) 0.0))
  (vla-put-rotation obj (+ cur-rot (* deg (/ pi 180.0))))
  (vla-update obj))

(defun BSW:print-status (name idx arrow)
  (princ (strcat "\n  " arrow "  " name
                 "  [" (itoa (1+ idx)) "/" (itoa (length *BSW:list*)) "]")))

(defun BSW:do-switch (sel-ent dir anchor arrow / cur-idx new-idx new-name new-obb)
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
     (setq new-obb (BSW:get-obb sel-ent))
     (BSW:draw-obb new-obb *BSW:color*)
     (BSW:print-status new-name new-idx arrow)
     new-obb)))

(defun BSW:do-move (sel-ent mm label / new-obb)
  (BSW:move-block sel-ent mm)
  (redraw)
  (setq new-obb (BSW:get-obb sel-ent))
  (BSW:draw-obb new-obb *BSW:color*)
  (princ (strcat "\n  " label "  " (rtos (abs mm) 2 0) "mm"))
  new-obb)

(defun BSW:do-updown (sel-ent mm label / new-obb)
  (BSW:move-updown sel-ent mm)
  (redraw)
  (setq new-obb (BSW:get-obb sel-ent))
  (BSW:draw-obb new-obb *BSW:color*)
  (princ (strcat "\n  " label "  " (rtos (abs mm) 2 0) "mm"))
  new-obb)

(defun BSW:do-rotate (sel-ent deg label / new-obb)
  (BSW:rotate-block sel-ent deg)
  (redraw)
  (setq new-obb (BSW:get-obb sel-ent))
  (BSW:draw-obb new-obb *BSW:color*)
  (princ (strcat "\n  " label))
  new-obb)

;; ============================================================
;; 메인 명령 : BS
;; ============================================================
(defun C:BS ( / sel-ent cur-obb grtype grval done result)
  (setq sel-ent nil cur-obb nil done nil)

  (princ "\n[BS]  클릭:선택  A:왼늘  S:왼줄  D:오줄  F:오늘")
  (princ "\n      Z:←500  X:←100  C:→100  V:→500  W:↑100  E:↓100  Q:CCW10  R:CW10  Space/ESC:종료")
  (princ (strcat "\n  목록: "
                 (apply 'strcat (mapcar '(lambda (b) (strcat b "  ")) *BSW:list*))))

  (while (not done)
    (setq grtype (car (setq _gr (grread T 4 0))) grval (cadr _gr))
    (cond

      ((= grtype 5) nil) ; 마우스 이동 무시

      ;; 마우스 클릭
      ((= grtype 3)
       (redraw)
       (setq cur-obb nil sel-ent nil)
       (setq sel-ent (BSW:find-nearest grval))
       (cond
         ((not sel-ent) (princ "\n  근처에 블럭이 없습니다."))
         ((= -1 (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*))
          (princ (strcat "\n  '" (cdr (assoc 2 (entget sel-ent))) "' 은(는) 목록에 없습니다."))
          (setq sel-ent nil))
         (T
          (setq cur-obb (BSW:get-obb sel-ent))
          (BSW:draw-obb cur-obb *BSW:color*)
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
         ;; A : 왼쪽 늘리기
         ((member grval '(65 97))
          (setq result (BSW:do-switch sel-ent 1 'R "<- 늘리기"))
          (if result (setq cur-obb result)))
         ;; S : 왼쪽 줄이기
         ((member grval '(83 115))
          (setq result (BSW:do-switch sel-ent -1 'R "-> 줄이기"))
          (if result (setq cur-obb result)))
         ;; D : 오른쪽 줄이기
         ((member grval '(68 100))
          (setq result (BSW:do-switch sel-ent -1 'L "<- 줄이기"))
          (if result (setq cur-obb result)))
         ;; F : 오른쪽 늘리기
         ((member grval '(70 102))
          (setq result (BSW:do-switch sel-ent 1 'L "-> 늘리기"))
          (if result (setq cur-obb result)))
         ;; Z : ←500mm
         ((member grval '(90 122))
          (setq result (BSW:do-move sel-ent -500 "<- 500mm"))
          (if result (setq cur-obb result)))
         ;; X : ←100mm
         ((member grval '(88 120))
          (setq result (BSW:do-move sel-ent -100 "<- 100mm"))
          (if result (setq cur-obb result)))
         ;; C : →100mm
         ((member grval '(67 99))
          (setq result (BSW:do-move sel-ent 100 "-> 100mm"))
          (if result (setq cur-obb result)))
         ;; V : →500mm
         ((member grval '(86 118))
          (setq result (BSW:do-move sel-ent 500 "-> 500mm"))
          (if result (setq cur-obb result)))
         ;; W : 화면 위로 100mm
         ((member grval '(87 119))
          (setq result (BSW:do-updown sel-ent 100 "↑ 100mm"))
          (if result (setq cur-obb result)))
         ;; E : 화면 아래로 100mm
         ((member grval '(69 101))
          (setq result (BSW:do-updown sel-ent -100 "↓ 100mm"))
          (if result (setq cur-obb result)))
         ;; Q : 반시계 10도 회전
         ((member grval '(81 113))
          (setq result (BSW:do-rotate sel-ent 10 "CCW 10deg"))
          (if result (setq cur-obb result)))
         ;; R : 시계 10도 회전
         ((member grval '(82 114))
          (setq result (BSW:do-rotate sel-ent -10 "CW 10deg"))
          (if result (setq cur-obb result)))
         ;; ESC / Space / Enter
         ((member grval '(27 32 13))
          (redraw) (setq done T) (princ "\n  종료.\n"))
       ))
    )
  )
  (princ))

(princ "\nBLKSWITCH 로드 완료 - 명령어: BS")
(princ)
