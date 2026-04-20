;;; ============================================================
;;; BLKSWITCH.LSP
;;; 화면 클릭으로 가장 가까운 블럭을 선택하고
;;; A 키 : 목록에서 이전 블럭으로 교체
;;; D 키 : 목록에서 다음 블럭으로 교체
;;; ESC  : 종료
;;; ============================================================

(vl-load-com)

;; ★★ 하이라이트 색상 (AutoCAD 색상 번호) ★★
;; 1=빨강  2=노랑  3=초록  4=하늘  5=파랑  6=보라  7=흰색
(setq *BSW:color* 3)

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

;;; 리스트에서 item 의 인덱스 반환 (없으면 -1)
(defun BSW:index-of (item lst / i)
  (setq i 0)
  (while (and lst (not (equal (car lst) item)))
    (setq lst (cdr lst) i (1+ i)))
  (if lst i -1))

;;; 점 pt 주변 윈도우에서 가장 가까운 INSERT 반환 (점점 확장)
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

;;; 블럭의 바운딩 박스 꼭짓점 4개 반환 (마진 없음)
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

;;; XOR 방식 사각 테두리 그리기 / 지우기 (같은 좌표로 두 번 호출 = 지우기)
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

;;; 상태 메시지 출력
(defun BSW:print-status (name idx arrow)
  (princ (strcat "\n  " arrow " " name
                 "  [" (itoa (1+ idx)) "/"
                 (itoa (length *BSW:list*)) "]")))

;; ============================================================
;; 메인 명령 : BLKSWITCH
;; ============================================================

(defun C:BS ( / sel-ent rect-pts grtype grval cur-idx new-idx new-name done)

  (setq sel-ent  nil
        rect-pts nil
        done     nil)

  (princ "\n[BS]  클릭:선택  A:이전  D:다음  ESC/Space/Enter:종료")
  (princ (strcat "\n  목록: "
                 (apply 'strcat
                        (mapcar '(lambda (b) (strcat b " ")) *BSW:list*))))

  (while (not done)
    (setq grtype (car  (setq _gr (grread T 4 0)))
          grval  (cadr _gr))

    (cond

      ;; 마우스 이동 : 무시
      ((= grtype 5) nil)

      ;; 마우스 클릭 : 가장 가까운 블럭 선택
      ((= grtype 3)
       (if rect-pts (BSW:draw-rect rect-pts *BSW:color*))   ; 기존 테두리 XOR 지우기
       (setq rect-pts nil sel-ent nil)

       (setq sel-ent (BSW:find-nearest grval))
       (cond
         ((not sel-ent)
          (princ "\n  근처에 블럭이 없습니다."))

         ((= -1 (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*))
          (princ (strcat "\n  '" (cdr (assoc 2 (entget sel-ent)))
                         "' 은(는) 목록에 없습니다."))
          (setq sel-ent nil))

         (T
          (setq rect-pts (BSW:get-corners sel-ent))
          (BSW:draw-rect rect-pts *BSW:color*)
          (BSW:print-status
            (cdr (assoc 2 (entget sel-ent)))
            (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*)
            "선택:"))))

      ;; 키보드 입력
      ((= grtype 2)
       (cond

         ;; A / a : 이전 블럭
         ((member grval '(65 97))
          (cond
            ((not sel-ent)
             (princ "\n  먼저 블럭을 클릭으로 선택하세요."))
            (T
             (setq cur-idx (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*))
             (cond
               ((= cur-idx -1) (princ "\n  선택한 블럭이 목록에 없습니다."))
               ((<= cur-idx 0) (princ "\n  이미 첫 번째 블럭입니다."))
               (T
                (setq new-idx (1- cur-idx) new-name (nth new-idx *BSW:list*))
                (BSW:set-name sel-ent new-name)  ; 블럭 교체 (내부적으로 화면 재렌더링)
                (redraw)                          ; grdraw 전부 제거 후 새로 시작
                (setq rect-pts (BSW:get-corners sel-ent))
                (BSW:draw-rect rect-pts *BSW:color*)
                (BSW:print-status new-name new-idx "<-"))))))

         ;; D / d : 다음 블럭
         ((member grval '(68 100))
          (cond
            ((not sel-ent)
             (princ "\n  먼저 블럭을 클릭으로 선택하세요."))
            (T
             (setq cur-idx (BSW:index-of (cdr (assoc 2 (entget sel-ent))) *BSW:list*))
             (cond
               ((= cur-idx -1) (princ "\n  선택한 블럭이 목록에 없습니다."))
               ((>= cur-idx (1- (length *BSW:list*))) (princ "\n  이미 마지막 블럭입니다."))
               (T
                (setq new-idx (1+ cur-idx) new-name (nth new-idx *BSW:list*))
                (BSW:set-name sel-ent new-name)  ; 블럭 교체 (내부적으로 화면 재렌더링)
                (redraw)                          ; grdraw 전부 제거 후 새로 시작
                (setq rect-pts (BSW:get-corners sel-ent))
                (BSW:draw-rect rect-pts *BSW:color*)
                (BSW:print-status new-name new-idx "->"))))))

         ;; ESC / 스페이스바 / 엔터 : 종료
         ((member grval '(27 32 13))
          (if rect-pts (BSW:draw-rect rect-pts *BSW:color*))
          (setq done T)
          (princ "\n  종료.\n"))

       )) ; end keyboard cond

    ) ; end main cond
  ) ; end while

  (princ))

(princ "\nBLKSWITCH 로드 완료 - 명령어: BS")
(princ)
