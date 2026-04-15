;;; ================================================================
;;; IC3D.LSP – 3D Interference Checker
;;; 명령어: IC3D
;;; AutoCAD 2011+  (getbbox, VLA 필요)
;;; ================================================================
(vl-load-com)

;;; ── 유틸: BBox 획득 (getbbox 우선, 실패시 VLA fallback) ──────────
(defun ic:get-bbox (ent / vobj mn mx res)
  (setq res (vl-catch-all-apply 'getbbox (list ent)))
  (if (vl-catch-all-error-p res)
    (progn                                     ; VLA fallback
      (setq vobj (vlax-ename->vla-object ent))
      (vla-getboundingbox vobj 'mn 'mx)
      (list (vlax-safearray->list mn)
            (vlax-safearray->list mx)))
    res)                                       ; (minpt maxpt)
)

;;; ── 유틸: INSERT → XREF 여부 ─────────────────────────────────────
(defun ic:xref-p (ent / bdef)
  (setq bdef (tblobjname "BLOCK" (cdr (assoc 2 (entget ent)))))
  (and bdef (/= 0 (logand 4 (cdr (assoc 70 (entget bdef))))))
)

;;; ── 유틸: 안전 삭제 ──────────────────────────────────────────────
(defun ic:safe-del (ent)
  (if (and ent (vl-catch-all-apply 'entget (list ent))
           (not (vl-catch-all-error-p
                  (vl-catch-all-apply 'entget (list ent)))))
    (entdel ent))
)

;;; ================================================================
;;; Phase 1: 객체 수집
;;; 반환: ((ename minpt maxpt objtype) ...)
;;; ================================================================
(defun ic:collect ( / ss i ent bbox etype rec lst)
  (setq lst '()
        ss  (ssget "_X" '((0 . "3DSOLID,INSERT"))))
  (if (null ss)
    (progn (princ "\n대상 객체 없음.") (return '())))
  (setq i 0)
  (while (< i (sslength ss))
    (setq ent  (ssname ss i)
          bbox (ic:get-bbox ent))
    (when bbox
      (setq etype (cdr (assoc 0 (entget ent))))
      (setq lst
        (cons (list ent
                    (car bbox)   ; minpt
                    (cadr bbox)  ; maxpt
                    (cond
                      ((= etype "3DSOLID") "3DSOLID")
                      ((ic:xref-p ent)    "XREF")
                      (T                  "INSERT")))
              lst)))
    (setq i (1+ i)))
  lst
)

;;; ================================================================
;;; Phase 2: Broad Phase – Sort-and-Sweep (X축)
;;; 반환: candidate pairs = ((rec_i rec_j) ...)
;;; ================================================================
(defun ic:broad-phase (obj-list / events active cands ev rec new-rec)
  (setq events '()  active '()  cands '())

  ;; 이벤트 생성: (x-val  type  record)   type 0=OPEN 1=CLOSE
  (foreach rec obj-list
    (setq events
      (cons (list (car (cadr rec))  0 rec) ; OPEN  at x_min
       (cons (list (car (caddr rec)) 1 rec) ; CLOSE at x_max
             events))))

  ;; X 정렬 (같은 X면 OPEN이 앞)
  (setq events
    (vl-sort events
      '(lambda (a b)
         (or (< (car a) (car b))
             (and (= (car a) (car b)) (< (cadr a) (cadr b)))))))

  (foreach ev events
    (setq rec (caddr ev))
    (cond
      ;; ── OPEN: 현재 active 전체와 Y/Z 겹침 검사
      ((= (cadr ev) 0)
       (setq new-rec rec)
       (foreach act active
         (when (ic:yz-overlap-p new-rec act)
           (setq cands (cons (list new-rec act) cands))))
       (setq active (cons new-rec active)))

      ;; ── CLOSE: active에서 제거
      ((= (cadr ev) 1)
       (setq active
         (vl-remove-if
           '(lambda (x) (equal (car x) (car rec)))
           active)))))
  cands
)

;;; Y/Z 축 겹침 판정 (rec = (ename minpt maxpt type))
(defun ic:yz-overlap-p (a b)
  (and (<= (cadr  (cadr a)) (cadr  (caddr b)))  ; a.min.y <= b.max.y
       (>= (cadr  (caddr a)) (cadr  (cadr b)))   ; a.max.y >= b.min.y
       (<= (caddr (cadr a)) (caddr (caddr b)))   ; a.min.z <= b.max.z
       (>= (caddr (caddr a)) (caddr (cadr b))))) ; a.max.z >= b.min.z

;;; ================================================================
;;; Phase 3-A: 3DSOLID ↔ 3DSOLID – INTERSECT Boolean
;;; 반환: 간섭 솔리드 ename | nil
;;; ================================================================
(defun ic:solid-check (e1 e2 / c1 c2 ss res vol)
  ;; 두 솔리드 복사
  (command "_.COPY" e1 "" "0,0,0" "0,0,0")  (setq c1 (entlast))
  (command "_.COPY" e2 "" "0,0,0" "0,0,0")  (setq c2 (entlast))

  ;; INTERSECT: c1이 교집합으로 수정, c2 소멸
  (setq ss (ssadd c1 (ssadd)))  (ssadd c2 ss)
  (vl-catch-all-apply 'command (list "_.INTERSECT" ss ""))

  ;; c2가 살아있으면 정리 (버전 따라 다름)
  (if (and c2 (not (vl-catch-all-error-p
                     (vl-catch-all-apply 'entget (list c2)))))
    (ic:safe-del c2))

  ;; c1 체적 확인
  (if (and c1 (not (vl-catch-all-error-p
                     (vl-catch-all-apply 'entget (list c1)))))
    (progn
      (setq vol (vl-catch-all-apply
                  'vlax-get
                  (list (vlax-ename->vla-object c1) 'Volume)))
      (cond
        ((vl-catch-all-error-p vol) (ic:safe-del c1) nil)
        ((> (abs vol) 1e-6) c1)          ; ← 간섭 솔리드 반환
        (T (ic:safe-del c1) nil)))
    nil)
)

;;; ================================================================
;;; Phase 3-B: INSERT / XREF 포함 쌍 – INTERFERE 명령 구동
;;; 반환: 간섭 솔리드 ename | nil
;;; ================================================================
(defun ic:insert-check (e1 e2 / ss1 ss2 snap)
  (setq ss1  (ssadd e1 (ssadd))
        ss2  (ssadd e2 (ssadd))
        snap (entlast))
  ;; INTERFERE: 세트1 / 세트2 / 간섭솔리드 생성=Yes
  (vl-catch-all-apply
    'command
    (list "_.INTERFERE" ss1 "" ss2 "" "Yes" ""))
  (if (not (equal (entlast) snap))
    (entlast)   ; 새로 생긴 간섭 솔리드
    nil)
)

;;; ================================================================
;;; Phase 3 전체
;;; ================================================================
(defun ic:narrow-phase (cands keep-solids / pair r1 r2 t1 t2 ifd results)
  (setq results '())
  (foreach pair cands
    (setq r1 (car pair)   r2 (cadr pair)
          t1 (cadddr r1)  t2 (cadddr r2))
    (setq ifd
      (if (and (= t1 "3DSOLID") (= t2 "3DSOLID"))
        (ic:solid-check  (car r1) (car r2))
        (ic:insert-check (car r1) (car r2))))
    (when ifd
      (unless keep-solids (ic:safe-del ifd))
      (setq results (cons (list (car r1) (car r2) t1 t2) results))))
  results
)

;;; ================================================================
;;; 결과 보고
;;; ================================================================
(defun ic:report (results n-objs n-cands)
  (textscr)
  (princ (strcat
    "\n\n══════════════════════════════════════════"
    "\n  [IC3D] 간섭 검사 결과"
    "\n══════════════════════════════════════════"
    "\n  검사 객체 수   : " (itoa n-objs)
    "\n  AABB 후보 쌍   : " (itoa n-cands)
    "\n  실제 간섭 쌍   : " (itoa (length results))
    "\n──────────────────────────────────────────"))
  (if (null results)
    (princ "\n  결과: 간섭 없음")
    (foreach r results
      (princ (strcat
        "\n  간섭: "
        (vl-princ-to-string (car  r)) " [" (caddr  r) "]"
        "  ↔  "
        (vl-princ-to-string (cadr r)) " [" (cadddr r) "]"))))
  (princ "\n══════════════════════════════════════════\n")
)

;;; ================================================================
;;; 메인 커맨드: IC3D
;;; ================================================================
(defun c:IC3D ( / *error* objs cands results keep)
  (defun *error* (msg)
    (unless (wcmatch (strcase msg) "*CANCEL*,*EXIT*,*QUIT*")
      (princ (strcat "\n[IC3D] 오류: " msg)))
    (command "_.UNDO" "E")
    (princ))

  (command "_.UNDO" "BE")
  (princ "\n[IC3D] 3D 간섭 검사")

  (initget "Yes No")
  (setq keep
    (= "Yes" (getkword "\n간섭 솔리드를 도면에 남기겠습니까? [Yes/No] <No>: ")))

  ;; Phase 1
  (princ "\n[1/3] 객체 수집 중...")
  (setq objs (ic:collect))
  (princ (strcat " → " (itoa (length objs)) "개 발견"))

  (if (< (length objs) 2)
    (princ "\n검사 가능한 객체가 2개 미만입니다.")
    (progn
      ;; Phase 2
      (princ "\n[2/3] Broad Phase (Sort & Sweep)...")
      (setq cands (ic:broad-phase objs))
      (princ (strcat " → 후보 " (itoa (length cands)) "쌍"))

      ;; Phase 3
      (princ "\n[3/3] Narrow Phase (Boolean 검사 중)...")
      (setq results (ic:narrow-phase cands keep))

      ;; 결과
      (ic:report results (length objs) (length cands))))

  (command "_.UNDO" "E")
  (princ)
)

(princ "\n[IC3D] 로드 완료 → 'IC3D' 명령 실행\n")