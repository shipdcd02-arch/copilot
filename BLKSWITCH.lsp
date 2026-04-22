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
;; ssget 필터 동적 생성
;; ============================================================
(defun BSW:build-filter (name-list / f)
  (setq f (list '(-4 . "<AND") '(0 . "INSERT") '(-4 . "<OR")))
  (foreach nm name-list (setq f (append f (list (cons 2 nm)))))
  (append f (list '(-4 . "OR>") '(-4 . "AND>"))))

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

(defun BSW:get-length-dir (ent / lx view-x)
  (setq lx     (car (BSW:local-axes ent))
        view-x (trans '(1.0 0.0 0.0) 2 0 T))
  (if (< (BSW:dot lx view-x) 0) (BSW:vec* -1.0 lx) lx))

(defun BSW:get-width-dir (ent / ly view-y)
  (setq ly     (nth 1 (BSW:local-axes ent))
        view-y (trans '(0.0 1.0 0.0) 2 0 T))
  (if (< (BSW:dot ly view-y) 0) (BSW:vec* -1.0 ly) ly))

;; ============================================================
;; OBB (앵커 계산용)
;; vla-getboundingbox 는 entmod 결과를 직접 읽으므로
;; entupd 없이도 최신 데이터 반영됨
;; ============================================================
(defun BSW:get-obb (ent / ed ed-tmp obj normal rot ax ay lx ly lz
                         mn-sa mx-sa mn mx corners cx cy cz ins3)
  (setq ed     (entget ent)
        obj    (vlax-ename->vla-object ent)
        normal (if (assoc 210 ed) (cdr (assoc 210 ed)) '(0.0 0.0 1.0))
        rot    (if (assoc 50  ed) (cdr (assoc 50  ed)) 0.0))
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
  (setq ins3   (trans (cdr (assoc 10 ed)) ent 0)
        normal (BSW:normalize normal))
  (if (and (< (abs (car normal)) 0.015625) (< (abs (cadr normal)) 0.015625))
    (setq ax (BSW:normalize (BSW:cross '(0.0 1.0 0.0) normal)))
    (setq ax (BSW:normalize (BSW:cross '(0.0 0.0 1.0) normal))))
  (setq ay      (BSW:normalize (BSW:cross normal ax))
        lx      (BSW:vec+ (BSW:vec* (cos rot) ax) (BSW:vec* (sin rot) ay))
        ly      (BSW:vec+ (BSW:vec* (- (sin rot)) ax) (BSW:vec* (cos rot) ay))
        lz      normal
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

;; ============================================================
;; 블럭 조작 - entmod 만 사용, entupd 는 do-all 에서 일괄 처리
;; ============================================================

;;; 블럭 교체 + 끝점 고정
;;; entmod 만 사용 → 화면 업데이트 없음 (do-switch-all 에서 일괄)
(defun BSW:switch-anchored (ent new-name anchor ldir
                            / ed old-obb new-obb old-proj new-proj
                              delta ins3-wcs new-ins-ocs)
  (setq ed      (entget ent)
        old-obb (BSW:get-obb ent))
  ;; 블럭명 변경 (vla-getboundingbox 는 entmod 후 직접 읽음)
  (entmod (subst (cons 2 new-name) (assoc 2 ed) ed))
  ;; 새 OBB → 앵커 보정
  (setq new-obb (BSW:get-obb ent))
  (if (= anchor 'R)
    (setq old-proj (BSW:proj-max old-obb ldir) new-proj (BSW:proj-max new-obb ldir))
    (setq old-proj (BSW:proj-min old-obb ldir) new-proj (BSW:proj-min new-obb ldir)))
  (setq delta       (- old-proj new-proj)
        ins3-wcs    (trans (cdr (assoc 10 (entget ent))) ent 0)
        new-ins-ocs (trans (BSW:vec+ ins3-wcs (BSW:vec* delta ldir)) 0 ent))
  ;; 삽입점 변경
  (entmod (subst (append '(10) new-ins-ocs) (assoc 10 (entget ent)) (entget ent))))

;;; 길이방향 이동
(defun BSW:move-block (ent ldir mm / ed ins3-wcs new-ins-ocs)
  (setq ed          (entget ent)
        ins3-wcs    (trans (cdr (assoc 10 ed)) ent 0)
        new-ins-ocs (trans (BSW:vec+ ins3-wcs (BSW:vec* mm ldir)) 0 ent))
  (entmod (subst (append '(10) new-ins-ocs) (assoc 10 ed) ed)))

;;; 폭방향 이동
(defun BSW:move-updown (ent wdir mm / ed ins3-wcs new-ins-ocs)
  (setq ed          (entget ent)
        ins3-wcs    (trans (cdr (assoc 10 ed)) ent 0)
        new-ins-ocs (trans (BSW:vec+ ins3-wcs (BSW:vec* mm wdir)) 0 ent))
  (entmod (subst (append '(10) new-ins-ocs) (assoc 10 ed) ed)))

;;; 회전
(defun BSW:rotate-block (ent deg / ed cur-rot new-rot)
  (setq ed      (entget ent)
        cur-rot (if (assoc 50 ed) (cdr (assoc 50 ed)) 0.0)
        new-rot (+ cur-rot (* deg (/ pi 180.0))))
  (entmod (if (assoc 50 ed)
            (subst (cons 50 new-rot) (assoc 50 ed) ed)
            (append ed (list (cons 50 new-rot))))))

;; ============================================================
;; 전체 블럭 일괄 처리 + entupd 일괄 → 화면은 호출부에서 한번에
;; block-data 구조: ((ent ldir wdir) ...)
;; ============================================================

(defun BSW:do-switch-all (block-data dir anchor arrow / ent ldir cur-idx new-idx new-name cnt)
  (setq cnt 0)
  (foreach bd block-data
    (setq ent (car bd) ldir (cadr bd)
          cur-idx (BSW:index-of (cdr (assoc 2 (entget ent))) *BSW:list*))
    (cond
      ((= cur-idx -1) nil)
      ((and (= dir  1) (>= cur-idx (1- (length *BSW:list*)))) nil)
      ((and (= dir -1) (<= cur-idx 0)) nil)
      (T (setq new-idx  (+ cur-idx dir)
               new-name (nth new-idx *BSW:list*))
         (BSW:switch-anchored ent new-name anchor ldir)
         (setq cnt (1+ cnt)))))
  ;; 전체 entupd 일괄
  (foreach bd block-data (entupd (car bd)))
  (if (> cnt 0)
    (princ (strcat "\n  " arrow "  " (itoa cnt) "개"))
    (princ (strcat "\n  " arrow "  변경 없음"))))

(defun BSW:do-move-all (block-data mm label)
  (foreach bd block-data (BSW:move-block (car bd) (cadr bd) mm))
  (foreach bd block-data (entupd (car bd)))
  (princ (strcat "\n  " label "  " (itoa (length block-data)) "개")))

(defun BSW:do-updown-all (block-data mm label)
  (foreach bd block-data (BSW:move-updown (car bd) (caddr bd) mm))
  (foreach bd block-data (entupd (car bd)))
  (princ (strcat "\n  " label "  " (itoa (length block-data)) "개")))

(defun BSW:do-rotate-all (block-data deg label)
  (foreach bd block-data (BSW:rotate-block (car bd) deg))
  (foreach bd block-data (entupd (car bd)))
  (princ (strcat "\n  " label "  " (itoa (length block-data)) "개")))

;; ============================================================
;; 메인 명령 : BS
;; ============================================================
(defun C:BS ( / flt ss sel-list block-data i ent grtype grval done)

  (setq flt (BSW:build-filter *BSW:list*))

  ;; 사전 선택(Pickfirst) 또는 직접 선택 - 목록 블럭만 허용
  (setq ss (ssget "_I" flt))
  (if (not ss)
    (progn
      (princ "\n블럭을 선택하세요 (Enter 로 완료): ")
      (setq ss (ssget flt))))

  (setq sel-list nil)
  (if ss
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq sel-list (cons (ssname ss i) sel-list))
        (setq i (1+ i)))))

  (if (not sel-list)
    (princ "\n  목록에 해당하는 블럭이 없습니다.")
    (progn
      ;; ★ 방향 벡터 한 번만 계산 ★
      (setq block-data
        (mapcar (function (lambda (ent)
                  (list ent
                        (BSW:get-length-dir ent)
                        (BSW:get-width-dir  ent))))
                sel-list))

      (princ (strcat "\n  " (itoa (length sel-list)) "개 블럭 선택됨"))
      (princ "\n  A:왼늘  S:왼줄  D:오줄  F:오늘")
      (princ "\n  Z:←500  X:←100  C:→100  V:→500")
      (princ "\n  W:폭↑100  E:폭↓100  Q:CCW10  R:CW10  Space/ESC:종료")

      ;; sssetfirst 로 선택 표시 유지
      (sssetfirst nil ss)

      (setq done nil)
      (while (not done)
        (setq grtype (car (setq _gr (grread nil 4 0)))
              grval  (cadr _gr))
        (cond
          ((= grtype 5) nil)
          ((= grtype 2)
           (cond
             ((member grval '(65 97))
              (BSW:do-switch-all block-data  1 'R "<- 늘리기")
              (redraw) (sssetfirst nil ss))
             ((member grval '(83 115))
              (BSW:do-switch-all block-data -1 'R "-> 줄이기")
              (redraw) (sssetfirst nil ss))
             ((member grval '(68 100))
              (BSW:do-switch-all block-data -1 'L "<- 줄이기")
              (redraw) (sssetfirst nil ss))
             ((member grval '(70 102))
              (BSW:do-switch-all block-data  1 'L "-> 늘리기")
              (redraw) (sssetfirst nil ss))
             ((member grval '(90 122))
              (BSW:do-move-all block-data -500 "<- 500mm")
              (redraw) (sssetfirst nil ss))
             ((member grval '(88 120))
              (BSW:do-move-all block-data -100 "<- 100mm")
              (redraw) (sssetfirst nil ss))
             ((member grval '(67 99))
              (BSW:do-move-all block-data  100 "-> 100mm")
              (redraw) (sssetfirst nil ss))
             ((member grval '(86 118))
              (BSW:do-move-all block-data  500 "-> 500mm")
              (redraw) (sssetfirst nil ss))
             ((member grval '(87 119))
              (BSW:do-updown-all block-data  100 "폭↑ 100mm")
              (redraw) (sssetfirst nil ss))
             ((member grval '(69 101))
              (BSW:do-updown-all block-data -100 "폭↓ 100mm")
              (redraw) (sssetfirst nil ss))
             ((member grval '(81 113))
              (BSW:do-rotate-all block-data  10 "CCW 10deg")
              (redraw) (sssetfirst nil ss))
             ((member grval '(82 114))
              (BSW:do-rotate-all block-data -10 "CW 10deg")
              (redraw) (sssetfirst nil ss))
             ((member grval '(27 32 13))
              (setq done T)
              (princ "\n  종료.\n"))))))))
  (princ))

(princ "\nBLKSWITCH 로드 완료 - 명령어: BS")
(princ)
