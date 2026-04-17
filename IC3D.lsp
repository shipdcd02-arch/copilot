;;; ================================================================
;;; IC3D.LSP  –  3D Interference Checker  (Memory-Optimized)
;;; ================================================================
;;; 명령어  : IC3D
;;; 요구사항: AutoCAD 2014+,  Visual LISP
;;;
;;; 메모리 최적화 핵심
;;;   - BVH 탐색 중 쌍을 리스트로 누적하지 않고 즉시 처리 (스트리밍)
;;;   - OBB 검사 시 코너 리스트 미생성, AABB 직접 축 투영
;;;   - leaf 순회에서 O(n) length 호출 제거
;;; ================================================================
(vl-load-com)
(if (not (boundp 'acIntersection)) (setq acIntersection 1))

(setq IC3D:LEAF-MAX  4)
(setq IC3D:BLKCACHE  nil)   ; ((blkname . T/nil) ...)  블록 3DSOLID 포함 여부 캐시
(setq IC3D:RESULTS   nil)   ; 간섭 확인된 쌍 결과
(setq IC3D:DONE      0)     ; 처리된 쌍 수 (진행률)
(setq IC3D:KEEP      nil)   ; 간섭 솔리드 보존 여부

;;; ================================================================
;;; § 유틸
;;; ================================================================

(defun ic:safe-del (e)
  (and e
       (not (vl-catch-all-error-p (vl-catch-all-apply 'entget (list e))))
       (entdel e)))

(defun ic:vla-copy (e)
  (vlax-vla-object->ename (vla-copy (vlax-ename->vla-object e))))

(defun ic:nth-pt (pt i)
  (cond ((= i 0) (car pt)) ((= i 1) (cadr pt)) (T (caddr pt))))

;;; 앞 n개 — reverse 생략 (BVH 분할은 순서 무관)
(defun ic:take (lst n / acc)
  (setq acc '())
  (while (and (> n 0) lst)
    (setq acc (cons (car lst) acc)  lst (cdr lst)  n (1- n)))
  acc)

(defun ic:drop (lst n)
  (while (and (> n 0) lst) (setq lst (cdr lst)  n (1- n)))
  lst)

;;; ================================================================
;;; § BBox 획득  (VLA GetBoundingBox)
;;; ================================================================
(defun ic:get-bbox (e / r mn mx)
  (setq r (vl-catch-all-apply 'vlax-ename->vla-object (list e)))
  (if (vl-catch-all-error-p r) nil
    (progn
      (setq r (vl-catch-all-apply 'vla-getboundingbox (list r 'mn 'mx)))
      (if (vl-catch-all-error-p r) nil
        (list (vlax-safearray->list mn)
              (vlax-safearray->list mx))))))

;;; ================================================================
;;; § Phase 1 : 객체 수집
;;; rec = (ename  minpt  maxpt  type  blkname-or-nil)
;;; blkname : INSERT/XREF 의 블록명, 3DSOLID 는 nil
;;; ================================================================
(defun ic:collect (ss / n i e ed bbox etype bname bdef lst)
  (setq lst '()  n (sslength ss)  i 0)
  (while (< i n)
    (setq e    (ssname ss i)
          ed   (entget e)
          bbox (ic:get-bbox e))
    (if bbox
      (progn
        (setq bname (cdr (assoc 2 ed)))
        (setq etype
          (cond
            ((= (cdr (assoc 0 ed)) "3DSOLID") "3DSOLID")
            ((and bname
                  (setq bdef (tblobjname "BLOCK" bname))
                  (/= 0 (logand 4 (cdr (assoc 70 (entget bdef))))))
             "XREF")
            (T "INSERT")))
        (setq lst
          (cons (list e (car bbox) (cadr bbox) etype
                      (if (= etype "3DSOLID") nil bname))
                lst))))
    (setq i (1+ i)))
  lst)

;;; rec 접근자
(defun ic:rec-ename   (r) (car r))
(defun ic:rec-min     (r) (cadr r))
(defun ic:rec-max     (r) (caddr r))
(defun ic:rec-type    (r) (cadddr r))
(defun ic:rec-blkname (r) (car (cddddr r)))

;;; ================================================================
;;; § Phase 2 : BVH 빌드
;;; 노드: (type  payload  mn  mx)
;;;   'L → payload = (rec ...)
;;;   'N → payload = (left-node right-node)
;;; ================================================================

(defun ic:aabb-union (recs / mn mx r)
  (setq mn (ic:rec-min (car recs))
        mx (ic:rec-max (car recs)))
  (foreach r (cdr recs)
    (setq mn (mapcar 'min mn (ic:rec-min r))
          mx (mapcar 'max mx (ic:rec-max r))))
  (list mn mx))

(defun ic:longest-axis (mn mx / d)
  (setq d (mapcar '- mx mn))
  (cond ((and (>= (car d) (cadr d)) (>= (car d) (caddr d))) 0)
        ((>= (cadr d) (caddr d)) 1)
        (T 2)))

(defun ic:rec-center (r axis)
  (* 0.5 (+ (ic:nth-pt (ic:rec-min r) axis)
            (ic:nth-pt (ic:rec-max r) axis))))

(defun ic:bvh-build (recs / aabb mn mx axis sorted mid)
  (setq aabb (ic:aabb-union recs)  mn (car aabb)  mx (cadr aabb))
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

(defun ic:nodes-overlap (na nb / mna mxa mnb mxb)
  (setq mna (caddr na)  mxa (cadddr na)
        mnb (caddr nb)  mxb (cadddr nb))
  ;; 등호 제외: 면이 맞닿기만 해도 후보에서 제외
  (and (< (car   mna) (car   mxb)) (> (car   mxa) (car   mnb))
       (< (cadr  mna) (cadr  mxb)) (> (cadr  mxa) (cadr  mnb))
       (< (caddr mna) (caddr mxb)) (> (caddr mxa) (caddr mnb))))

;;; ================================================================
;;; § Mid-Filter 함수들
;;; ================================================================

;;; ── 필터 A : 블록 콘텐츠 캐시 ───────────────────────────────────
(defun ic:block-has-solid (blkname / cached e ed result)
  (setq cached (assoc blkname IC3D:BLKCACHE))
  (if cached
    (cdr cached)
    (progn
      (setq e (tblobjname "BLOCK" blkname)  result nil)
      (if e
        (progn
          (setq e (entnext e))
          (while (and e (not result))
            (setq ed (entget e))
            (cond
              ((= (cdr (assoc 0 ed)) "3DSOLID")
               (setq result T))
              ((= (cdr (assoc 0 ed)) "INSERT")
               (setq result (ic:block-has-solid (cdr (assoc 2 ed))))))
            (if (not result) (setq e (entnext e))))))
      (setq IC3D:BLKCACHE (cons (cons blkname result) IC3D:BLKCACHE))
      result)))

;;; ── 필터 B : 경계구체 ────────────────────────────────────────────
(defun ic:sphere-pass-p (r1 r2 / mn1 mx1 mn2 mx2 cx1 cy1 cz1 cx2 cy2 cz2
                                   dx dy dz rx ry rz rad1 rad2 sumR)
  (setq mn1 (ic:rec-min r1)  mx1 (ic:rec-max r1)
        mn2 (ic:rec-min r2)  mx2 (ic:rec-max r2))
  ;; 중심
  (setq cx1 (* 0.5 (+ (car mn1) (car mx1)))
        cy1 (* 0.5 (+ (cadr mn1) (cadr mx1)))
        cz1 (* 0.5 (+ (caddr mn1) (caddr mx1)))
        cx2 (* 0.5 (+ (car mn2) (car mx2)))
        cy2 (* 0.5 (+ (cadr mn2) (cadr mx2)))
        cz2 (* 0.5 (+ (caddr mn2) (caddr mx2))))
  ;; 반지름 (bbox 대각선 절반)
  (setq rx (- (car mx1) (car mn1))
        ry (- (cadr mx1) (cadr mn1))
        rz (- (caddr mx1) (caddr mn1))
        rad1 (* 0.5 (sqrt (+ (* rx rx) (* ry ry) (* rz rz)))))
  (setq rx (- (car mx2) (car mn2))
        ry (- (cadr mx2) (cadr mn2))
        rz (- (caddr mx2) (caddr mn2))
        rad2 (* 0.5 (sqrt (+ (* rx rx) (* ry ry) (* rz rz)))))
  ;; 중심간 거리² < (r1+r2)²  — 등호 제외 (외접 구체끼리 맞닿음 제외)
  (setq dx (- cx1 cx2)  dy (- cy1 cy2)  dz (- cz1 cz2)
        sumR (+ rad1 rad2))
  (< (+ (* dx dx) (* dy dy) (* dz dz)) (* sumR sumR)))

;;; ── 필터 C : OBB SAT ─────────────────────────────────────────────
;;; 코너 리스트 미생성 — AABB를 축에 직접 투영
;;; AABB (mn,mx) 를 2D 축 (ax,ay) 에 투영한 [min, max] 구간
(defun ic:aabb-proj (mn mx ax ay / px1 px2 py1 py2)
  (setq px1 (* ax (car mn))   px2 (* ax (car mx))
        py1 (* ay (cadr mn))  py2 (* ay (cadr mx)))
  (list (+ (min px1 px2) (min py1 py2))
        (+ (max px1 px2) (max py1 py2))))

;;; 축(ax,ay)에서 두 AABB가 분리되면 T
;;; 등호 포함(>=): 투영 구간이 딱 맞닿기만 해도 분리로 처리
(defun ic:sat-sep-p (mn1 mx1 mn2 mx2 ax ay / p1 p2)
  (setq p1 (ic:aabb-proj mn1 mx1 ax ay)
        p2 (ic:aabb-proj mn2 mx2 ax ay))
  (or (>= (car p1) (cadr p2))
      (>= (car p2) (cadr p1))))

;;; OBB 통과 여부 (회전 INSERT 의 로컬 X/Y 축으로 SAT)
(defun ic:obb-pass-p (r1 r2 / t1 t2 angle ed ca sa mn1 mx1 mn2 mx2)
  (setq t1 (ic:rec-type r1)  t2 (ic:rec-type r2)
        mn1 (ic:rec-min r1)  mx1 (ic:rec-max r1)
        mn2 (ic:rec-min r2)  mx2 (ic:rec-max r2))
  (cond
    ((and (or (= t1 "INSERT") (= t1 "XREF"))
          (setq ed (entget (ic:rec-ename r1)))
          (setq angle (cdr (assoc 50 ed)))
          angle  (/= angle 0.0))
     (setq ca (cos angle)  sa (sin angle))
     (not (or (ic:sat-sep-p mn1 mx1 mn2 mx2    ca      sa)
              (ic:sat-sep-p mn1 mx1 mn2 mx2 (- sa)     ca))))
    ((and (or (= t2 "INSERT") (= t2 "XREF"))
          (setq ed (entget (ic:rec-ename r2)))
          (setq angle (cdr (assoc 50 ed)))
          angle  (/= angle 0.0))
     (setq ca (cos angle)  sa (sin angle))
     (not (or (ic:sat-sep-p mn1 mx1 mn2 mx2    ca      sa)
              (ic:sat-sep-p mn1 mx1 mn2 mx2 (- sa)     ca))))
    (T T)))

;;; ================================================================
;;; § Narrow Phase 함수들
;;; ================================================================

(defun ic:solid-check (e1 e2 / c1 c2 v1 vol res)
  (setq c1 (ic:vla-copy e1)
        c2 (ic:vla-copy e2)
        v1 (vlax-ename->vla-object c1))
  (setq res (vl-catch-all-apply
               'vla-boolean (list v1 acIntersection
                                  (vlax-ename->vla-object c2))))
  (if (and c2 (not (vl-catch-all-error-p
                     (vl-catch-all-apply 'entget (list c2)))))
    (ic:safe-del c2))
  (cond
    ((vl-catch-all-error-p res) (ic:safe-del c1) nil)
    (T
     (setq vol (vl-catch-all-apply 'vlax-get (list v1 'Volume)))
     (if (and (not (vl-catch-all-error-p vol)) (> (abs vol) 1e-6))
       c1
       (progn (ic:safe-del c1) nil)))))

(defun ic:insert-check (e1 e2 / ss1 ss2 snap)
  (setq ss1  (ssadd e1 (ssadd))
        ss2  (ssadd e2 (ssadd))
        snap (entlast))
  (vl-catch-all-apply
    'command (list "_.INTERFERE" ss1 "" ss2 "" "Yes" ""))
  (if (not (equal (entlast) snap)) (entlast) nil))

;;; ================================================================
;;; § 스트리밍 처리 핵심
;;; BVH 탐색 중 쌍 발견 즉시 필터+Boolean 수행
;;; 쌍 리스트를 메모리에 누적하지 않음
;;; ================================================================

(defun ic:check-pair (r1 r2 / t1 t2 bname ifd)
  (setq t1 (ic:rec-type r1)  t2 (ic:rec-type r2))
  (cond
    ;; 필터 A-1: r1 블록에 3DSOLID 없음
    ((and (or (= t1 "INSERT") (= t1 "XREF"))
          (setq bname (ic:rec-blkname r1))
          (not (ic:block-has-solid bname)))
     nil)
    ;; 필터 A-2: r2 블록에 3DSOLID 없음
    ((and (or (= t2 "INSERT") (= t2 "XREF"))
          (setq bname (ic:rec-blkname r2))
          (not (ic:block-has-solid bname)))
     nil)
    ;; 필터 B: 경계구체
    ((not (ic:sphere-pass-p r1 r2)) nil)
    ;; 필터 C: OBB SAT
    ((not (ic:obb-pass-p r1 r2)) nil)
    ;; Boolean 검사
    (T
     (setq ifd
       (if (and (= t1 "3DSOLID") (= t2 "3DSOLID"))
         (ic:solid-check  (ic:rec-ename r1) (ic:rec-ename r2))
         (ic:insert-check (ic:rec-ename r1) (ic:rec-ename r2))))
     (if ifd
       (progn
         (if (not IC3D:KEEP) (ic:safe-del ifd))
         (setq IC3D:RESULTS
           (cons (list (ic:rec-ename r1) (ic:rec-ename r2) t1 t2)
                 IC3D:RESULTS))))
     (setq IC3D:DONE (1+ IC3D:DONE))
     (if (= 0 (rem IC3D:DONE 10))
       (princ (strcat "\r  Boolean 처리: " (itoa IC3D:DONE) "쌍..."))))))

;;; ── BVH 스트리밍 탐색 ────────────────────────────────────────────

;;; 리프 내부 쌍: (and recs (cdr recs)) 로 O(1) 종료 판정
(defun ic:bvh-leaf-stream (recs / head tail)
  (while (and recs (cdr recs))
    (setq head (car recs)  tail (cdr recs))
    (foreach r tail (ic:check-pair head r))
    (setq recs tail)))

;;; 두 서브트리 간 교차 쌍 (AABB 가지치기 포함)
(defun ic:bvh-cross-stream (na nb / da db)
  (cond
    ((not (ic:nodes-overlap na nb)) nil)
    ((and (= (car na) 'L) (= (car nb) 'L))
     (foreach ra (cadr na)
       (foreach rb (cadr nb) (ic:check-pair ra rb))))
    ((= (car na) 'L)
     (setq db (cadr nb))
     (ic:bvh-cross-stream na (car  db))
     (ic:bvh-cross-stream na (cadr db)))
    ((= (car nb) 'L)
     (setq da (cadr na))
     (ic:bvh-cross-stream (car  da) nb)
     (ic:bvh-cross-stream (cadr da) nb))
    (T
     (setq da (cadr na)  db (cadr nb))
     (ic:bvh-cross-stream (car  da) (car  db))
     (ic:bvh-cross-stream (car  da) (cadr db))
     (ic:bvh-cross-stream (cadr da) (car  db))
     (ic:bvh-cross-stream (cadr da) (cadr db)))))

;;; 자기충돌 탐색 진입점
(defun ic:bvh-self-stream (node / da)
  (if (= (car node) 'L)
    (ic:bvh-leaf-stream (cadr node))
    (progn
      (setq da (cadr node))
      (ic:bvh-self-stream (car  da))
      (ic:bvh-self-stream (cadr da))
      (ic:bvh-cross-stream (car da) (cadr da)))))

;;; ================================================================
;;; § 결과 보고
;;; ================================================================
(defun ic:report (results na nb layer-a layer-b / n r layer-of)
  ;; ename → 레이어명 반환 헬퍼
  (defun layer-of (e) (cdr (assoc 8 (entget e))))
  (textscr)
  (princ
    (strcat
      "\n\n══════════════════════════════════════════"
      "\n  [IC3D] 두 그룹 간 간섭 검사 결과"
      "\n══════════════════════════════════════════"
      "\n  그룹 A [" layer-a "] : " (itoa na) "개"
      "\n  그룹 B [" layer-b "] : " (itoa nb) "개"
      "\n  Boolean 실행          : " (itoa IC3D:DONE) "쌍"
      "\n  실제 간섭             : " (itoa (length results)) "쌍"
      "\n──────────────────────────────────────────"))
  (if (null results)
    (princ "\n  결과: 간섭 없음")
    (progn
      (setq n 1)
      (foreach r results
        ;; r = (ename1 ename2 type1 type2)
        (princ
          (strcat "\n  [" (itoa n) "]"
                  "  A:" (vl-princ-to-string (car  r))
                         " (" (caddr  r) "/" (layer-of (car  r)) ")"
                  "  ↔"
                  "  B:" (vl-princ-to-string (cadr r))
                         " (" (cadddr r) "/" (layer-of (cadr r)) ")"))
        (setq n (1+ n)))))
  (princ "\n══════════════════════════════════════════\n"))

;;; ================================================================
;;; § 레이어 선택 헬퍼
;;; 객체 클릭 → 레이어 자동 인식
;;; 또는 Enter → 직접 입력 (와일드카드 * 사용 가능)
;;; ================================================================
(defun ic:pick-layer (group-label / sel layer)
  (princ (strcat "\n[그룹 " group-label "] 레이어 대표 객체 클릭"
                 "  (Enter = 레이어명 직접 입력):"))
  (setq sel (entsel))
  (if sel
    (progn
      (setq layer (cdr (assoc 8 (entget (car sel)))))
      (princ (strcat "  → 레이어: \"" layer "\""))
      layer)
    (progn
      (princ (strcat "\n[그룹 " group-label "] 레이어명"
                     " (와일드카드 * 사용 가능): "))
      (getstring T))))

;;; ================================================================
;;; § 메인 커맨드  IC3D
;;; 두 레이어 그룹 선택 → 그룹 간 교차 검사만 수행
;;; 같은 그룹 내부는 BVH 구조상 비교 자체가 발생하지 않음
;;; ================================================================
(defun c:IC3D ( / *error* layer-a layer-b ssA ssB objsA objsB rootA rootB)
  (defun *error* (msg)
    (setvar "REGENMODE" 1)
    (setvar "HIGHLIGHT" 1)
    (if (not (wcmatch (strcase msg) "*CANCEL*,*EXIT*,*QUIT*"))
      (princ (strcat "\n[IC3D] 오류: " msg)))
    (command "_.UNDO" "E")
    (princ))

  (command "_.UNDO" "BE")

  ;; 전역 상태 초기화
  (setq IC3D:BLKCACHE nil
        IC3D:RESULTS  nil
        IC3D:DONE     0)

  (princ "\n[IC3D] 3D 간섭 검사 (레이어 두 그룹 비교)")

  ;; ── 레이어 선택
  (setq layer-a (ic:pick-layer "A"))
  (if (= layer-a "")
    (progn (princ "\n  그룹 A 레이어 없음. 취소.") (command "_.UNDO" "E") (princ))
    (progn
      (setq layer-b (ic:pick-layer "B"))
      (if (= layer-b "")
        (progn (princ "\n  그룹 B 레이어 없음. 취소.") (command "_.UNDO" "E") (princ))
        (progn

          ;; ── 레이어로 선택셋 구성
          (setq ssA (ssget "_X" (list (cons 0 "3DSOLID,INSERT")
                                      (cons 8 layer-a)))
                ssB (ssget "_X" (list (cons 0 "3DSOLID,INSERT")
                                      (cons 8 layer-b))))

          (cond
            ((null ssA) (princ (strcat "\n  그룹 A [" layer-a "] 객체 없음.")))
            ((null ssB) (princ (strcat "\n  그룹 B [" layer-b "] 객체 없음.")))
            (T
             (initget "Yes No")
             (setq IC3D:KEEP
               (= "Yes"
                  (getkword
                    "\n간섭 솔리드를 도면에 남기겠습니까? [Yes/No] <No>: ")))

             ;; ── Phase 1: 수집
             (princ "\n[1/3] 객체 수집 중...")
             (setq objsA (ic:collect ssA)
                   objsB (ic:collect ssB))
             (princ (strcat "  A=" (itoa (length objsA))
                            "개  B=" (itoa (length objsB)) "개"))

             (if (or (null objsA) (null objsB))
               (princ "\n  한 그룹 이상 객체가 없습니다.")
               (progn
                 ;; ── Phase 2: 각 그룹 별도 BVH 빌드
                 (princ "\n[2/3] BVH 빌드 중...")
                 (setq rootA (ic:bvh-build objsA)
                       rootB (ic:bvh-build objsB))
                 (princ " 완료")

                 ;; ── Phase 3: 그룹 간 교차 스트리밍만 실행
                 ;;  ic:bvh-cross-stream 은 두 트리 간 쌍만 생성
                 ;;  → 같은 그룹 내 비교는 구조상 발생 불가
                 (princ "\n[3/3] 교차 간섭 검사 중...")
                 (setvar "REGENMODE" 0)
                 (setvar "HIGHLIGHT" 0)
                 (ic:bvh-cross-stream rootA rootB)
                 (setvar "REGENMODE" 1)
                 (setvar "HIGHLIGHT" 1)

                 (ic:report IC3D:RESULTS
                            (length objsA) (length objsB)
                            layer-a layer-b))))))

          (command "_.UNDO" "E")
          (princ))))))

(princ "\n[IC3D] 로드 완료.  명령어: IC3D\n")
