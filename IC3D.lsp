;;; ================================================================
;;; IC3D.LSP  –  3D Interference Checker  (Optimized / Large Drawing)
;;; ================================================================
;;; 명령어  : IC3D
;;; 요구사항: AutoCAD 2011+,  Visual LISP
;;;
;;; 파이프라인
;;;   Phase 1. 수집    ssget "_X" → 3DSOLID / INSERT / XREF
;;;   Phase 2. Broad   BVH(자기충돌) → 중복없는 후보 쌍
;;;   Phase 3. Narrow  3D↔3D : vla-boolean(Intersect)
;;;                    Block/XREF 포함 : INTERFERE 명령
;;; ================================================================
(vl-load-com)

;;; vla-boolean Operation 값  (AcBooleanType: Union=0 Intersection=1 Subtraction=2)
(if (not (boundp 'acIntersection)) (setq acIntersection 1))

;;; BVH 리프 한계 (이 수 이하면 리프 노드)
(setq IC3D:LEAF-MAX 4)

;;; ================================================================
;;; § 유틸
;;; ================================================================

(defun ic:safe-del (e)
  (and e
       (not (vl-catch-all-error-p (vl-catch-all-apply 'entget (list e))))
       (entdel e)))

(defun ic:vla-copy (e)
  (vlax-vla-object->ename (vla-copy (vlax-ename->vla-object e))))

;;; nth 대신 (car/cadr/caddr) 쓰기 어려운 자리에 사용
(defun ic:nth-pt (pt i)
  (cond ((= i 0) (car pt)) ((= i 1) (cadr pt)) (T (caddr pt))))

(defun ic:take (lst n)
  (if (or (zerop n) (null lst)) '()
    (cons (car lst) (ic:take (cdr lst) (1- n)))))

(defun ic:drop (lst n)
  (if (or (zerop n) (null lst)) lst (ic:drop (cdr lst) (1- n))))

;;; ================================================================
;;; § BBox 획득  (VLA GetBoundingBox)
;;; 반환: (minpt maxpt)  실패 시 nil
;;; ================================================================
(defun ic:get-bbox (e / r mn mx)
  (setq r (vl-catch-all-apply 'vlax-ename->vla-object (list e)))
  (if (vl-catch-all-error-p r)
    nil
    (progn
      (setq r (vl-catch-all-apply 'vla-getboundingbox (list r 'mn 'mx)))
      (if (vl-catch-all-error-p r)
        nil
        (list (vlax-safearray->list mn)
              (vlax-safearray->list mx))))))

;;; ================================================================
;;; § Phase 1 : 객체 수집
;;; rec = (ename  minpt  maxpt  type)
;;;       type : "3DSOLID" | "INSERT" | "XREF"
;;; ================================================================
(defun ic:collect ( / ss n i e ed bbox bname bdef lst)
  (setq lst '()
        ss  (ssget "_X" '((0 . "3DSOLID,INSERT"))))
  (if (null ss)
    (progn (princ "\n  대상 객체 없음.") lst)
    (progn
      (setq n (sslength ss)  i 0)
      (while (< i n)
        (setq e    (ssname ss i)
              ed   (entget e)
              bbox (ic:get-bbox e))
        (if bbox
          (progn
            (setq bname (cdr (assoc 2 ed)))
            (setq lst
              (cons
                (list e (car bbox) (cadr bbox)
                  (cond
                    ((= (cdr (assoc 0 ed)) "3DSOLID") "3DSOLID")
                    ((and bname
                          (setq bdef (tblobjname "BLOCK" bname))
                          (/= 0 (logand 4 (cdr (assoc 70 (entget bdef))))))
                     "XREF")
                    (T "INSERT")))
                lst))))
        (setq i (1+ i)))
      lst)))

;;; ================================================================
;;; § Phase 2 : BVH Broad Phase
;;;
;;; 노드 구조: (type  payload  mn  mx)
;;;   type = 'L  →  payload = (rec ...)          ← 리프
;;;   type = 'N  →  payload = (left-node right-node)  ← 내부
;;; ================================================================

;;; ── AABB 합집합 ──────────────────────────────────────────────────
(defun ic:aabb-union (recs / mn mx r)
  (setq mn (cadr (car recs))
        mx (caddr (car recs)))
  (foreach r (cdr recs)
    (setq mn (mapcar 'min mn (cadr r))
          mx (mapcar 'max mx (caddr r))))
  (list mn mx))

;;; ── 가장 긴 축 (0=X 1=Y 2=Z) ────────────────────────────────────
(defun ic:longest-axis (mn mx / d)
  (setq d (mapcar '- mx mn))
  (cond ((and (>= (car d) (cadr d)) (>= (car d) (caddr d))) 0)
        ((>= (cadr d) (caddr d)) 1)
        (T 2)))

;;; ── rec 중심 좌표 (axis 방향) ────────────────────────────────────
(defun ic:rec-center (r axis)
  (* 0.5 (+ (ic:nth-pt (cadr r) axis)
            (ic:nth-pt (caddr r) axis))))

;;; ── BVH 빌드 (재귀) ──────────────────────────────────────────────
(defun ic:bvh-build (recs / aabb mn mx axis sorted mid)
  (setq aabb (ic:aabb-union recs)
        mn   (car aabb)
        mx   (cadr aabb))
  (if (<= (length recs) IC3D:LEAF-MAX)
    (list 'L recs mn mx)
    (progn
      (setq axis   (ic:longest-axis mn mx)
            sorted (vl-sort recs
                     (function (lambda (a b)
                       (< (ic:rec-center a axis)
                          (ic:rec-center b axis)))))
            mid    (/ (length sorted) 2))
      (list 'N
            (list (ic:bvh-build (ic:take sorted mid))
                  (ic:bvh-build (ic:drop sorted mid)))
            mn mx))))

;;; ── 두 노드 AABB 겹침 판정 ───────────────────────────────────────
(defun ic:nodes-overlap (na nb / mna mxa mnb mxb)
  (setq mna (caddr na)  mxa (cadddr na)
        mnb (caddr nb)  mxb (cadddr nb))
  (and (<= (car   mna) (car   mxb)) (>= (car   mxa) (car   mnb))
       (<= (cadr  mna) (cadr  mxb)) (>= (cadr  mxa) (cadr  mnb))
       (<= (caddr mna) (caddr mxb)) (>= (caddr mxa) (caddr mnb))))

;;; ── 리프 내부 쌍 ─────────────────────────────────────────────────
(defun ic:leaf-pairs (recs acc / first rest)
  (if (< (length recs) 2) acc
    (progn
      (setq first (car recs)  rest (cdr recs))
      (foreach r rest (setq acc (cons (list first r) acc)))
      (ic:leaf-pairs rest acc))))

;;; ── Cross 쌍 : 두 서브트리 간 (중복 없음) ───────────────────────
(defun ic:bvh-cross (na nb acc / da db)
  (cond
    ((not (ic:nodes-overlap na nb)) acc)
    ((and (= (car na) 'L) (= (car nb) 'L))
     (foreach ra (cadr na)
       (foreach rb (cadr nb)
         (setq acc (cons (list ra rb) acc))))
     acc)
    ((= (car na) 'L)
     (setq db (cadr nb))
     (setq acc (ic:bvh-cross na (car  db) acc))
     (ic:bvh-cross            na (cadr db) acc))
    ((= (car nb) 'L)
     (setq da (cadr na))
     (setq acc (ic:bvh-cross (car  da) nb acc))
     (ic:bvh-cross            (cadr da) nb acc))
    (T
     (setq da (cadr na)  db (cadr nb))
     (setq acc (ic:bvh-cross (car  da) (car  db) acc))
     (setq acc (ic:bvh-cross (car  da) (cadr db) acc))
     (setq acc (ic:bvh-cross (cadr da) (car  db) acc))
     (ic:bvh-cross            (cadr da) (cadr db) acc))))

;;; ── 자기충돌 탐색 (중복 쌍 생성 없음) ───────────────────────────
(defun ic:bvh-self (node acc / da)
  (if (= (car node) 'L)
    (ic:leaf-pairs (cadr node) acc)
    (progn
      (setq da  (cadr node)
            acc (ic:bvh-self (car  da) acc)
            acc (ic:bvh-self (cadr da) acc))
      (ic:bvh-cross (car da) (cadr da) acc))))

;;; ── Broad Phase 진입점 ───────────────────────────────────────────
(defun ic:broad-phase (obj-list)
  (if (< (length obj-list) 2) '()
    (ic:bvh-self (ic:bvh-build obj-list) '())))

;;; ================================================================
;;; § Phase 3 : Narrow Phase
;;; ================================================================

;;; ── 3DSOLID ↔ 3DSOLID  (VLA Boolean — 커맨드 프로세서 우회) ─────
(defun ic:solid-check (e1 e2 / c1 c2 v1 vol res)
  (setq c1 (ic:vla-copy e1)
        c2 (ic:vla-copy e2)
        v1 (vlax-ename->vla-object c1))
  ;; vla-boolean: c1 = c1 ∩ c2,  c2 소멸
  (setq res (vl-catch-all-apply
               'vla-boolean (list v1 acIntersection
                                  (vlax-ename->vla-object c2))))
  ;; c2가 아직 살아있으면 제거 (버전 차이 대비)
  (if (and c2 (not (vl-catch-all-error-p
                     (vl-catch-all-apply 'entget (list c2)))))
    (ic:safe-del c2))
  (cond
    ;; 에러 = 교집합 없음
    ((vl-catch-all-error-p res) (ic:safe-del c1) nil)
    (T
     (setq vol (vl-catch-all-apply 'vlax-get (list v1 'Volume)))
     (if (and (not (vl-catch-all-error-p vol)) (> (abs vol) 1e-6))
       c1                         ; 간섭 솔리드 반환 (caller가 관리)
       (progn (ic:safe-del c1) nil)))))

;;; ── INSERT / XREF 포함 쌍  (INTERFERE 명령 구동) ─────────────────
(defun ic:insert-check (e1 e2 / ss1 ss2 snap)
  (setq ss1  (ssadd e1 (ssadd))
        ss2  (ssadd e2 (ssadd))
        snap (entlast))
  (vl-catch-all-apply
    'command (list "_.INTERFERE" ss1 "" ss2 "" "Yes" ""))
  (if (not (equal (entlast) snap)) (entlast) nil))

;;; ── 후보 쌍 배치 처리 ────────────────────────────────────────────
(defun ic:narrow-phase (cands keep / r1 r2 t1 t2 ifd results done total)
  (setq results '()
        done    0
        total   (length cands))
  ;; 화면 갱신 억제 → narrow phase 동안 리제너/하이라이트 끔
  (setvar "REGENMODE" 0)
  (setvar "HIGHLIGHT" 0)
  (foreach pair cands
    (setq r1 (car pair)  r2 (cadr pair)
          t1 (cadddr r1) t2 (cadddr r2))
    (setq ifd
      (if (and (= t1 "3DSOLID") (= t2 "3DSOLID"))
        (ic:solid-check  (car r1) (car r2))
        (ic:insert-check (car r1) (car r2))))
    (when ifd
      (if (not keep) (ic:safe-del ifd))
      (setq results (cons (list (car r1) (car r2) t1 t2) results)))
    (setq done (1+ done))
    ;; 진행률 (50쌍마다 표시)
    (when (zerop (rem done 50))
      (princ (strcat "\r  " (itoa done) " / " (itoa total) " 쌍 처리 중..."))))
  (setvar "REGENMODE" 1)
  (setvar "HIGHLIGHT" 1)
  results)

;;; ================================================================
;;; § 결과 보고
;;; ================================================================
(defun ic:report (results n-objs n-cands / n)
  (textscr)
  (princ
    (strcat
      "\n\n══════════════════════════════════════════"
      "\n  [IC3D] 간섭 검사 결과"
      "\n══════════════════════════════════════════"
      "\n  검사 객체 수  : " (itoa n-objs)
      "\n  AABB 후보 쌍  : " (itoa n-cands)
      "\n  실제 간섭 쌍  : " (itoa (length results))
      "\n──────────────────────────────────────────"))
  (if (null results)
    (princ "\n  결과: 간섭 없음")
    (progn
      (setq n 1)
      (foreach r results
        (princ
          (strcat "\n  [" (itoa n) "]  "
                  (vl-princ-to-string (car  r)) " (" (caddr  r) ")"
                  "  ↔  "
                  (vl-princ-to-string (cadr r)) " (" (cadddr r) ")"))
        (setq n (1+ n)))))
  (princ "\n══════════════════════════════════════════\n"))

;;; ================================================================
;;; § 메인 커맨드  IC3D
;;; ================================================================
(defun c:IC3D ( / *error* objs cands results keep)
  (defun *error* (msg)
    (setvar "REGENMODE" 1)
    (setvar "HIGHLIGHT" 1)
    (if (not (wcmatch (strcase msg) "*CANCEL*,*EXIT*,*QUIT*"))
      (princ (strcat "\n[IC3D] 오류: " msg)))
    (command "_.UNDO" "E")
    (princ))

  (command "_.UNDO" "BE")
  (princ "\n[IC3D] 3D 간섭 검사 (대형 도면 최적화)")

  (initget "Yes No")
  (setq keep
    (= "Yes"
       (getkword "\n간섭 솔리드를 도면에 남기겠습니까? [Yes/No] <No>: ")))

  ;; ── Phase 1
  (princ "\n[1/3] 객체 수집 중...")
  (setq objs (ic:collect))
  (princ (strcat " → " (itoa (length objs)) "개 발견"))

  (if (< (length objs) 2)
    (princ "\n  검사 가능한 객체가 2개 미만입니다.")
    (progn
      ;; ── Phase 2
      (princ "\n[2/3] BVH 브로드 페이즈...")
      (setq cands (ic:broad-phase objs))
      (princ (strcat " → 후보 " (itoa (length cands)) "쌍"))

      ;; ── Phase 3
      (princ "\n[3/3] 내로우 페이즈 (VLA Boolean / INTERFERE)...")
      (setq results (ic:narrow-phase cands keep))

      ;; ── Report
      (ic:report results (length objs) (length cands))))

  (command "_.UNDO" "E")
  (princ))

(princ "\n[IC3D] 로드 완료.  명령어: IC3D\n")
