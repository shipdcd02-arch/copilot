;;; ============================================================
;;; BLKSWITCH.LSP
;;; 명령 실행 전 또는 후에 블럭을 선택하면
;;; 선택된 모든 블럭에 키 조작이 동시 적용됩니다.
;;;
;;; A:왼늘  S:왼줄  D:오줄  F:오늘
;;; Z:←500  X:←100  C:→100  V:→500
;;; W:폭위100  E:폭아래100  Q:CCW10  R:CW10
;;; Space / ESC / Enter : 종료
;;; ============================================================

(vl-load-com)

;; ★★ 블럭 목록 - 짧은 것부터 긴 순서로 입력하세요 ★★
(setq *BSW:list* '("1M" "1.5M" "2M" "2.5M" "3M"))

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
;; 블럭 로컬 축 (임의축 알고리즘 + rotation)
;; ============================================================
(defun BSW:local-axes (ent / ed normal rot ax ay)
  (setq ed     (entget ent)
        normal (BSW:normalize
                 (if (assoc 210 ed) (cdr (assoc 210 ed)) '(0.0 0.0 1.0)))
        rot    (if (assoc 50 ed) (cdr (assoc 50 ed)) 0.0))
  (if (and (< (abs (car normal)) 0.015625) (< (abs (cadr normal)) 0.015625))
    (setq ax (BSW:normalize (BSW:cross '(0.0 1.0 0.0) normal)))
    (setq ax (BSW:normalize (BSW:cross '(0.0 0.0 1.0) normal))))
  (setq ay (BSW:normalize (BSW:cross normal ax)))
  (list
    (BSW:vec+ (BSW:vec* (cos rot) ax) (BSW:vec* (sin rot) ay))
    (BSW:vec+ (BSW:vec* (- (sin rot)) ax) (BSW:vec* (cos rot) ay))
    normal))

;;; 블럭 길이방향 (뷰 오른쪽 기준으로 정렬)
(defun BSW:get-length-dir (ent / lx view-x)
  (setq lx     (car (BSW:local-axes ent))
        view-x (trans '(1.0 0.0 0.0) 2 0 T))
  (if (< (BSW:dot lx view-x) 0) (BSW:vec* -1.0 lx) lx))

;;; 블럭 폭방향 (로컬 Y축, 뷰 위쪽 기준으로 정렬)
(defun BSW:get-width-dir (ent / ly view-y)
  (setq ly     (nth 1 (BSW:local-axes ent))
        view-y (trans '(0.0 1.0 0.0) 2 0 T))
  (if (< (BSW:dot ly view-y) 0) (BSW:vec* -1.0 ly) ly))

;; ============================================================
;; OBB - 앵커 계산용 (블럭 교체 시 끝점 고정에 사용)
;; ============================================================
(defun BSW:get-obb (ent / ed ed-tmp obj normal rot ax ay lx ly lz
                         mn-sa mx-sa mn mx corners cx cy cz ins3)
  (setq ed     (entget ent)
        obj    (vlax-ename->vla-object ent)
        normal (if (assoc 210 ed) (cdr (assoc 210 ed)) '(0.0 0.0 1.0))
        rot    (if (assoc 50  ed) (cdr (assoc 50  ed)) 0.0))
  ;; 임시: ins=원점 rot=0 normal=(0,0,1) → 로컬 bbox
  (setq ed-tmp ed
        ed-tmp (subst '(10 0.0 0.0 0.0) (assoc 10 ed-tmp) ed-tmp)
        ed-tmp (if (assoc 50  ed-tmp)
                 (subst (cons 50 0.0) (assoc 50 ed-tmp) ed-tmp)
                 (append ed-tmp (list (cons 50 0.0))))
        ed-tmp (if (assoc 210 ed-tmp)
                 (subst '(210 0.0 0.0 1.0) (assoc 210 ed-tmp) ed-tmp)
                 (append ed-tmp (list '(210 0.0 0.0 1.0)))))
  (entmod ed-tmp)
  (if (not (vl-catch-all-error-p
             (vl-catch-all-apply 'vla-getboundingbox (list obj 'mn-sa 'mx-sa))))
    (setq mn (vlax-safearray->list mn-sa) mx (vlax-safearray->list mx-sa))
    (setq mn '(-0.5 -0.5 -0.5) mx '(0.5 0.5 0.5)))
  (entmod ed)
  ;; WCS 삽입점
  (setq ins3 (trans (cdr (assoc 10 ed)) ent 0))
  ;; 실제 로컬 축
  (setq normal (BSW:normalize normal))
  (if (and (< (abs (car normal)) 0.015625) (< (abs (cadr normal)) 0.015625))
    (setq ax (BSW:normalize (BSW:cross '(0.0 1.0 0.0) normal)))
    (setq ax (BSW:normalize (BSW:cross '(0.0 0.0 1.0) normal))))
  (setq ay (BSW:normalize (BSW:cross normal ax))
        lx (BSW:vec+ (BSW:vec* (cos rot) ax) (BSW:vec* (sin rot) ay))
        ly (BSW:vec+ (BSW:vec* (- (sin rot)) ax) (BSW:vec* (cos rot) ay))
        lz normal
        corners nil)
  (foreach cx (list (car mn) (car mx))
    (foreach cy (list (cadr mn) (cadr mx))
      (foreach cz (list (caddr mn) (caddr mx))
        (setq corners (cons
          (BSW:vec+ ins3 (BSW:vec+ (BSW:vec* cx lx)
                          (BSW:vec+ (BSW:vec* cy ly) (BSW:vec* cz lz))))
          corners)))))
  (reverse corners))

(defun BSW:proj-max (corners dir)
  (apply 'max (mapcar (function (lambda (p) (BSW:dot dir p))) corners)))
(defun BSW:proj-min (corners dir)
  (apply 'min (mapcar (function (lambda (p) (BSW:dot dir p))) corners)))

;; ============================================================
;; 헬퍼
;; ============================================================
(defun BSW:index-of (item lst / i)
  (setq i 0)
  (while (and lst (not (equal (car lst) item)))
    (setq lst (cdr lst) i (1+ i)))
  (if lst i -1))

;;; 블럭 교체 + 길이방향 한쪽 끝 고정
(defun BSW:switch-anchored (ent new-name anchor
                            / obj ldir old-obb new-obb old-proj new-proj delta ins3)
  (setq obj     (vlax-ename->vla-object ent)
        ldir    (BSW:get-length-dir ent)
        old-obb (BSW:get-obb ent))
  (vla-put-name obj new-name)
  (vla-update obj)
  (setq new-obb (BSW:get-obb ent))
  (if (= anchor 'R)
    (setq old-proj (BSW:proj-max old-obb ldir) new-proj (BSW:proj-max new-obb ldir))
    (setq old-proj (BSW:proj-min old-obb ldir) new-proj (BSW:proj-min new-obb ldir)))
  (setq delta (- old-proj new-proj)
        ins3  (trans (cdr (assoc 10 (entget ent))) ent 0))
  (vla-put-insertionpoint obj (vlax-3d-point (BSW:vec+ ins3 (BSW:vec* delta ldir))))
  (vla-update obj))

;;; 길이방향 이동
(defun BSW:move-block (ent mm / obj ldir ins3)
  (setq obj  (vlax-ename->vla-object ent)
        ldir (BSW:get-length-dir ent)
        ins3 (trans (cdr (assoc 10 (entget ent))) ent 0))
  (vla-put-insertionpoint obj (vlax-3d-point (BSW:vec+ ins3 (BSW:vec* mm ldir))))
  (vla-update obj))

;;; 폭방향 이동
(defun BSW:move-updown (ent mm / obj wdir ins3)
  (setq obj  (vlax-ename->vla-object ent)
        wdir (BSW:get-width-dir ent)
        ins3 (trans (cdr (assoc 10 (entget ent))) ent 0))
  (vla-put-insertionpoint obj (vlax-3d-point (BSW:vec+ ins3 (BSW:vec* mm wdir))))
  (vla-update obj))

;;; 회전
(defun BSW:rotate-block (ent deg / obj cur-rot)
  (setq obj     (vlax-ename->vla-object ent)
        cur-rot (if (assoc 50 (entget ent)) (cdr (assoc 50 (entget ent))) 0.0))
  (vla-put-rotation obj (+ cur-rot (* deg (/ pi 180.0))))
  (vla-update obj))

;; ============================================================
;; 선택된 전체 블럭에 적용하는 함수들
;; ============================================================

(defun BSW:do-switch-all (sel-list dir anchor arrow / ent cur-idx new-idx new-name cnt)
  (setq cnt 0)
  (foreach ent sel-list
    (setq cur-idx (BSW:index-of (cdr (assoc 2 (entget ent))) *BSW:list*))
    (cond
      ((= cur-idx -1) nil)
      ((and (= dir  1) (>= cur-idx (1- (length *BSW:list*)))) nil)
      ((and (= dir -1) (<= cur-idx 0)) nil)
      (T
       (setq new-idx  (+ cur-idx dir)
             new-name (nth new-idx *BSW:list*))
       (BSW:switch-anchored ent new-name anchor)
       (setq cnt (1+ cnt)))))
  (if (> cnt 0)
    (princ (strcat "\n  " arrow "  " (itoa cnt) "개"))
    (princ (strcat "\n  " arrow "  변경 없음"))))

(defun BSW:do-move-all (sel-list mm label / ent)
  (foreach ent sel-list (BSW:move-block ent mm))
  (princ (strcat "\n  " label "  " (itoa (length sel-list)) "개")))

(defun BSW:do-updown-all (sel-list mm label / ent)
  (foreach ent sel-list (BSW:move-updown ent mm))
  (princ (strcat "\n  " label "  " (itoa (length sel-list)) "개")))

(defun BSW:do-rotate-all (sel-list deg label / ent)
  (foreach ent sel-list (BSW:rotate-block ent deg))
  (princ (strcat "\n  " label "  " (itoa (length sel-list)) "개")))

;; ============================================================
;; 메인 명령 : BS
;; ============================================================
(defun C:BS ( / ss sel-list i ent grtype grval done)

  ;; 사전 선택(Pickfirst) 확인 → 없으면 직접 선택 요청
  (setq ss (ssget "_I" '((0 . "INSERT"))))
  (if (not ss)
    (progn
      (princ "\n블럭을 선택하세요 (Enter 로 완료): ")
      (setq ss (ssget '((0 . "INSERT"))))))

  ;; 목록에 있는 블럭만 필터링
  (setq sel-list nil)
  (if ss
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq ent (ssname ss i))
        (if (member (cdr (assoc 2 (entget ent))) *BSW:list*)
          (setq sel-list (cons ent sel-list)))
        (setq i (1+ i)))))

  (if (not sel-list)
    (princ "\n  목록에 해당하는 블럭이 없습니다.")
    (progn
      (princ (strcat "\n  " (itoa (length sel-list)) "개 블럭 선택됨"))
      (princ "\n  A:왼늘  S:왼줄  D:오줄  F:오늘")
      (princ "\n  Z:←500  X:←100  C:→100  V:→500")
      (princ "\n  W:폭↑100  E:폭↓100  Q:CCW10  R:CW10  Space/ESC:종료")

      (setq done nil)
      (while (not done)
        (setq grtype (car (setq _gr (grread nil 4 0)))
              grval  (cadr _gr))
        (cond
          ((= grtype 5) nil)
          ((= grtype 2)
           (cond
             ;; A : 왼쪽 늘리기
             ((member grval '(65 97))  (BSW:do-switch-all sel-list  1 'R "<- 늘리기"))
             ;; S : 왼쪽 줄이기
             ((member grval '(83 115)) (BSW:do-switch-all sel-list -1 'R "-> 줄이기"))
             ;; D : 오른쪽 줄이기
             ((member grval '(68 100)) (BSW:do-switch-all sel-list -1 'L "<- 줄이기"))
             ;; F : 오른쪽 늘리기
             ((member grval '(70 102)) (BSW:do-switch-all sel-list  1 'L "-> 늘리기"))
             ;; Z : ←500mm
             ((member grval '(90 122)) (BSW:do-move-all sel-list -500 "<- 500mm"))
             ;; X : ←100mm
             ((member grval '(88 120)) (BSW:do-move-all sel-list -100 "<- 100mm"))
             ;; C : →100mm
             ((member grval '(67 99))  (BSW:do-move-all sel-list  100 "-> 100mm"))
             ;; V : →500mm
             ((member grval '(86 118)) (BSW:do-move-all sel-list  500 "-> 500mm"))
             ;; W : 폭방향 +100mm
             ((member grval '(87 119)) (BSW:do-updown-all sel-list  100 "폭↑ 100mm"))
             ;; E : 폭방향 -100mm
             ((member grval '(69 101)) (BSW:do-updown-all sel-list -100 "폭↓ 100mm"))
             ;; Q : 반시계 10도
             ((member grval '(81 113)) (BSW:do-rotate-all sel-list  10 "CCW 10deg"))
             ;; R : 시계 10도
             ((member grval '(82 114)) (BSW:do-rotate-all sel-list -10 "CW 10deg"))
             ;; ESC / Space / Enter
             ((member grval '(27 32 13))
              (setq done T)
              (princ "\n  종료.\n"))))))))
  (princ))

(princ "\nBLKSWITCH 로드 완료 - 명령어: BS")
(princ)
