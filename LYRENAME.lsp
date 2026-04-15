;;; ============================================================
;;;  LYRENAME.LSP  -  레이어 이름 일괄 변경 유틸리티 v2
;;;  명령어: LYRENAME
;;; ============================================================
(vl-load-com)

;;;─── 전체 레이어 이름 목록 (알파벳 정렬) ─────────────────────
(defun lyr:get-all (/ lyr acc)
  (setq acc '())
  (setq lyr (tblnext "LAYER" T))
  (while lyr
    (setq acc (cons (cdr (assoc 2 lyr)) acc))
    (setq lyr (tblnext "LAYER"))
  )
  (vl-sort acc '(lambda (a b) (< (strcase a) (strcase b))))
)

;;;─── 키워드 포함 필터 (대소문자 무시) ────────────────────────
(defun lyr:filter (kw lst)
  (if (= kw "")
    lst
    (vl-remove-if-not
      '(lambda (n) (wcmatch (strcase n) (strcat "*" (strcase kw) "*")))
      lst)
  )
)

;;;─── 문자열 전체 치환 (대소문자 무시 검색, 원본 케이스 보존) ─
(defun lyr:replace-all (old new s / pos res)
  (if (or (= old "") (not (vl-string-search (strcase old) (strcase s))))
    s
    (progn
      (setq res "")
      (while (setq pos (vl-string-search (strcase old) (strcase s)))
        (setq res (strcat res (substr s 1 pos) new))
        (setq s (substr s (+ pos (strlen old) 1)))
      )
      (strcat res s)
    )
  )
)

;;;─── 키워드 등장 횟수 ─────────────────────────────────────────
(defun lyr:count-occur (old s / pos cnt)
  (setq cnt 0)
  (if (not (= old ""))
    (progn
      (setq pos 0)
      (while (setq pos (vl-string-search (strcase old) (strcase s) pos))
        (setq cnt (1+ cnt)
              pos (1+ pos))
      )
    )
  )
  cnt
)

;;;─── 선택 인덱스 문자열 "0 2 5" → 정수 리스트 ───────────────
(defun lyr:parse-sel (str / v)
  (if (or (null str) (= str "")) '()
    (progn
      (setq v (read (strcat "(" str ")")))
      (if (listp v) v (list v))
    )
  )
)

;;;─── 인덱스 리스트 → 레이어명 리스트 ────────────────────────
(defun lyr:idx->names (indices lst)
  (mapcar '(lambda (i) (nth i lst)) indices)
)

;;;─── 레이어명 리스트 → 인덱스 리스트 (대상 리스트 기준) ─────
(defun lyr:names->idx (names lst / idx res)
  (setq res '() idx 0)
  (foreach item lst
    (if (member item names)
      (setq res (append res (list idx)))
    )
    (setq idx (1+ idx))
  )
  res
)

;;;─── 인덱스 리스트 → 공백 구분 문자열 ───────────────────────
(defun lyr:idx->str (indices / res)
  (setq res "")
  (foreach i indices
    (setq res (strcat res (if (= res "") "" " ") (itoa i)))
  )
  res
)

;;;─── 공통 최장 부분 문자열 (대소문자 무시) ───────────────────
;;; 리스트의 모든 항목에 포함된 가장 긴 공통 문자열 반환
(defun lyr:common-substr (str-list / sorted s1 n len start sub found result)
  (cond
    ((null str-list) "")
    ((= (length str-list) 1) (car str-list))
    (T
      ;; 가장 짧은 문자열부터 검색
      (setq sorted (vl-sort (append str-list nil)
                    '(lambda (a b) (< (strlen a) (strlen b)))))
      (setq s1 (car sorted)
            n  (strlen s1)
            result "")
      (setq len n)
      (while (and (> len 0) (= result ""))
        (setq start 1)
        (while (and (<= start (+ (- n len) 1)) (= result ""))
          (setq sub (substr s1 start len)
                found T)
          (foreach s str-list
            (if (not (vl-string-search (strcase sub) (strcase s)))
              (setq found nil)
            )
          )
          (if found (setq result sub))
          (setq start (1+ start))
        )
        (setq len (1- len))
      )
      result
    )
  )
)

;;;─── 리스트박스 내용 갱신 ────────────────────────────────────
(defun lyr:refresh-list (lst)
  (start_list "layer_list" 2)
  (if lst (mapcar 'add_list lst))
  (end_list)
)

;;;─── 선택 이벤트 처리 ────────────────────────────────────────
;;; 필터로 숨겨진 선택 유지 + 공통 키워드 자동계산 + 보호 로직
(defun lyr:on-select (sel-str / new-vis hidden new-all common)
  ;; 현재 필터 기준으로 새로 선택된 이름
  (setq new-vis (lyr:idx->names (lyr:parse-sel sel-str) *lyr:filtered*))
  ;; 필터로 숨겨진 기존 선택은 유지
  (setq hidden
    (vl-remove-if '(lambda (n) (member n *lyr:filtered*)) *lyr:sel_names*))
  (setq new-all (append new-vis hidden))

  (cond
    ;; ── 수동 모드: 키워드 건드리지 않고 이름만 업데이트 ────────
    (*lyr:kw_manual*
     (setq *lyr:sel_names* new-all))

    ;; ── 자동 모드 ──────────────────────────────────────────────
    ;; 선택 전체 해제
    ((null new-all)
     (setq *lyr:sel_names* '()
           *lyr:before* "")
     (set_tile "before_name" ""))

    ;; 공통 문자열 있음 → 키워드 업데이트
    ((not (= (setq common (lyr:common-substr new-all)) ""))
     (setq *lyr:sel_names* new-all
           *lyr:before* common)
     (set_tile "before_name" common))

    ;; 공통 없음 & 기존 키워드 있음 → 보호 (새 선택 무시)
    ((not (= *lyr:before* ""))
     (set_tile "layer_list"
       (lyr:idx->str (lyr:names->idx *lyr:sel_names* *lyr:filtered*))))

    ;; 공통 없음 & 기존 키워드도 없음 → 그냥 업데이트
    (T
     (setq *lyr:sel_names* new-all
           *lyr:before* "")
     (set_tile "before_name" ""))
  )
  (set_tile "sel_count"
    (strcat "선택: " (itoa (length *lyr:sel_names*)) " 개"))
)

;;;─── 필터 이벤트 처리 ────────────────────────────────────────
;;; 표시 목록 갱신 후 기존 선택 복원
(defun lyr:on-filter (kw / restore-idx)
  (setq *lyr:filter_kw* kw
        *lyr:filtered*  (lyr:filter kw *lyr:all*))
  (lyr:refresh-list *lyr:filtered*)
  ;; 기존 선택 중 현재 필터에 보이는 항목만 복원
  (setq restore-idx (lyr:names->idx *lyr:sel_names* *lyr:filtered*))
  (set_tile "layer_list" (lyr:idx->str restore-idx))
  (set_tile "sel_count"
    (strcat "선택: " (itoa (length *lyr:sel_names*)) " 개"))
)

;;;─── DCL 파일 생성 ────────────────────────────────────────────
(defun lyr:write-dcl (fpath / fp)
  (setq fp (open fpath "w"))
  (foreach s
    (list
      "layer_rename : dialog {"
      "  label = \"레이어 이름 변경 유틸리티\";"
      "  : boxed_row {"
      "    label = \"변경 설정\";"
      "    : column {"
      "      : text { label = \"변경 전  (포함 키워드):\"; }"
      "      : edit_box { key = \"before_name\"; edit_width = 22; }"
      "    }"
      "    : column {"
      "      : text { label = \"변경 후  (교체 텍스트):\"; }"
      "      : edit_box { key = \"after_name\"; edit_width = 22; }"
      "    }"
      "  }"
      "  : row {"
      "    : text { label = \"레이어 필터 :\"; width = 13; fixed_width = true; }"
      "    : edit_box { key = \"filter_name\"; edit_width = 47; }"
      "  }"
      "  : text { label = \"레이어 목록  (Ctrl/Shift: 다중선택  |  필터: Enter/Tab)\"; }"
      "  : list_box {"
      "    key             = \"layer_list\";"
      "    height          = 13;"
      "    width           = 62;"
      "    multiple_select = true;"
      "  }"
      "  : row {"
      "    : text { key = \"sel_count\"; label = \"선택: 0 개\"; width = 36; }"
      "    : spacer {}"
      "  }"
      "  : row {"
      "    : button { key = \"btn_convert\"; label = \"  변  환  \";"
      "               width = 14; is_default = true; }"
      "    : spacer {}"
      "    : button { key = \"cancel\"; label = \"  취  소  \";"
      "               width = 14; is_cancel = true; }"
      "  }"
      "  errtile;"
      "}"
      ""
      "confirm_dlg : dialog {"
      "  label = \"변환 확인\";"
      "  : text { key = \"confirm_warn\"; label = \" \"; }"
      "  : text { label = \"변환될 레이어 목록:\"; }"
      "  : list_box {"
      "    key             = \"confirm_list\";"
      "    height          = 12;"
      "    width           = 62;"
      "    multiple_select = false;"
      "  }"
      "  : row {"
      "    : button { key = \"accept\"; label = \"  변환 실행  \";"
      "               is_default = true; width = 16; }"
      "    : spacer {}"
      "    : button { key = \"cancel\"; label = \"  취  소  \";"
      "               is_cancel = true; width = 16; }"
      "  }"
      "}"
    )
    (write-line s fp)
  )
  (close fp)
)

;;;─── 확인 다이얼로그 (변환 전 최종 검토) ─────────────────────
(defun lyr:show-confirm (dcl_id items warn-msg)
  (if (not (new_dialog "confirm_dlg" dcl_id))
    (progn (alert "확인 다이얼로그를 열 수 없습니다.") nil)
    (progn
      (set_tile "confirm_warn" warn-msg)
      (start_list "confirm_list" 2)
      (mapcar 'add_list items)
      (end_list)
      (action_tile "accept" "(done_dialog 1)")
      (action_tile "cancel" "(done_dialog 0)")
      (= (start_dialog) 1)
    )
  )
)

;;;─── 메인 명령 ───────────────────────────────────────────────
(defun c:LYRENAME (/ dcl_file dcl_id ret
                      confirm-items warn-msg need-warn
                      cnt old-n new-n occur label errs msg)

  ;; ── 전역 상태 초기화 ──────────────────────────────────────
  (setq *lyr:all*       (lyr:get-all)  ; 전체 레이어 목록
        *lyr:filtered*  *lyr:all*      ; 필터 후 표시 목록 (처음엔 전체)
        *lyr:sel_names* '()            ; 선택된 레이어 이름 목록
        *lyr:before*    ""             ; 변경 전 키워드
        *lyr:after*     ""             ; 변경 후 텍스트
        *lyr:kw_manual* nil            ; T=수동입력, nil=자동채움
        *lyr:filter_kw* "")            ; 필터 키워드

  ;; ── DCL 생성 & 로드 ───────────────────────────────────────
  (setq dcl_file (strcat (getvar "TEMPPREFIX") "lyrename_tmp.dcl"))
  (lyr:write-dcl dcl_file)
  (setq dcl_id (load_dialog dcl_file))
  (if (not (new_dialog "layer_rename" dcl_id))
    (progn (alert "다이얼로그를 열 수 없습니다.") (exit))
  )

  ;; ── 초기 상태: 전체 레이어 표시 ──────────────────────────
  (lyr:refresh-list *lyr:all*)
  (set_tile "sel_count" "선택: 0 개")

  ;; ── 타일 이벤트 ───────────────────────────────────────────

  ;; [변경 전] 사용자 직접 입력 → 수동 모드 전환
  ;; 비우면 자동 모드로 복귀
  (action_tile "before_name"
    "(progn
       (setq *lyr:before* $value)
       (setq *lyr:kw_manual* (not (= *lyr:before* \"\"))))"
  )

  ;; [변경 후] 입력
  (action_tile "after_name"
    "(setq *lyr:after* $value)"
  )

  ;; [레이어 필터] - Enter 또는 Tab 으로 적용
  (action_tile "filter_name"
    "(lyr:on-filter $value)"
  )

  ;; 리스트 선택 변경
  (action_tile "layer_list"
    "(lyr:on-select $value)"
  )

  ;; [변환] 버튼 - 기본 유효성 검사 후 닫기
  (action_tile "btn_convert"
    "(cond
       ((= *lyr:before* \"\")
        (set_tile \"error\"
          \"[변경 전] 키워드를 입력하거나 레이어를 선택하세요.\"))
       ((null *lyr:sel_names*)
        (set_tile \"error\"
          \"목록에서 레이어를 하나 이상 선택하세요.\"))
       (T (done_dialog 1)))"
  )

  (action_tile "cancel" "(done_dialog 0)")

  (setq ret (start_dialog))

  ;; ── 변환 처리 ─────────────────────────────────────────────
  (if (= ret 1)
    (progn
      ;; 확인 목록 구성 + 경고 플래그 계산
      (setq confirm-items '()
            need-warn     nil)

      (foreach lyr-n *lyr:sel_names*
        (setq new-n  (lyr:replace-all *lyr:before* *lyr:after* lyr-n)
              occur  (lyr:count-occur *lyr:before* lyr-n))
        (setq label
          (cond
            ;; 키워드 미포함
            ((= occur 0)
             (setq need-warn T)
             (strcat "  [키워드 없음] " lyr-n "  (변경 안됨)"))
            ;; 키워드 2회 이상 포함
            ((> occur 1)
             (setq need-warn T)
             (strcat "  [" (itoa occur) "회 포함] " lyr-n
                     "  ->  " new-n))
            ;; 정상
            (T
             (strcat "  " lyr-n "  ->  " new-n))
          )
        )
        (setq confirm-items (append confirm-items (list label)))
      )

      ;; 확인 다이얼로그 표시 (항상)
      (setq warn-msg
        (if need-warn
          (strcat "[!] 경고 항목이 포함되어 있습니다. "
                  "계속 진행하시겠습니까?")
          (strcat (itoa (length *lyr:sel_names*))
                  " 개 레이어를 변환합니다. 내용을 확인하세요.")
        )
      )

      (if (lyr:show-confirm dcl_id confirm-items warn-msg)
        ;; ── 실제 이름 변경 ──────────────────────────────────
        (progn
          (setq cnt 0
                errs "")
          (foreach lyr-n *lyr:sel_names*
            (setq old-n lyr-n
                  new-n (lyr:replace-all *lyr:before* *lyr:after* old-n)
                  occur (lyr:count-occur *lyr:before* old-n))
            (cond
              ;; 키워드 없는 레이어 스킵
              ((= occur 0) nil)
              ;; 결과가 동일하면 스킵
              ((equal old-n new-n) nil)
              ;; 이름 충돌
              ((tblsearch "LAYER" new-n)
               (setq errs
                 (strcat errs "\n  " old-n " -> " new-n "  (이름 충돌)")))
              ;; 정상 변경
              (T
               (vl-cmdf "-LAYER" "RENAME" old-n new-n "")
               (setq cnt (1+ cnt)))
            )
          )
          (setq msg
            (strcat (itoa cnt) " 개 레이어 이름이 변경되었습니다."))
          (if (not (= errs ""))
            (setq msg (strcat msg "\n\n[오류]" errs)))
          (alert msg)
        )
        ;; ── 취소 ──────────────────────────────────────────
        (princ "\n변환이 취소되었습니다.")
      )
    )
  )

  (unload_dialog dcl_id)
  (princ)
)

(princ "\n>> 명령어 [LYRENAME] 으로 레이어 이름 변경 유틸리티를 실행합니다.")
(princ)
