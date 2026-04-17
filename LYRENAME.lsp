;;; ============================================================
;;;  LYRENAME.LSP  -  레이어 이름 일괄 변경 유틸리티 v3
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

;;;─── 0 ~ (n-1) 정수 리스트 생성 ─────────────────────────────
(defun lyr:range (n / i res)
  (setq i 0 res '())
  (repeat n
    (setq res (append res (list i))
          i   (1+ i))
  )
  res
)

;;;─── 두 리스트 합집합 (순서 유지, 중복 제거) ────────────────
(defun lyr:union (lst1 lst2 / res)
  (setq res lst1)
  (foreach item lst2
    (if (not (member item res))
      (setq res (append res (list item)))
    )
  )
  res
)

;;;─── 공통 최장 부분 문자열 (대소문자 무시) ───────────────────
(defun lyr:common-substr (str-list / sorted s1 n len start sub found result)
  (cond
    ((null str-list) "")
    ((= (length str-list) 1) (car str-list))
    (T
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

;;;─── 리스트박스 내용 갱신 (mode 3 = 전체 삭제 후 추가) ───────
(defun lyr:refresh-list (lst)
  (start_list "layer_list" 3)
  (if lst (mapcar 'add_list lst))
  (end_list)
)

;;;─── 선택 수 표시 갱신 ───────────────────────────────────────
(defun lyr:update-count ()
  (set_tile "sel_count"
    (strcat (itoa (length *lyr:sel_names*)) " 개 선택됨"))
)

;;;─── 선택 이벤트 처리 ────────────────────────────────────────
;;; *lyr:in-select* 플래그로 set_tile 에 의한 재귀 진입 방지
(defun lyr:on-select (sel-str / new-vis hidden new-all common)
  (if *lyr:in-select* (exit))                  ; 재진입 시 즉시 탈출
  (setq *lyr:in-select* T)
  (setq new-vis (lyr:idx->names (lyr:parse-sel sel-str) *lyr:filtered*))
  (setq hidden
    (vl-remove-if '(lambda (n) (member n *lyr:filtered*)) *lyr:sel_names*))
  (setq new-all (append new-vis hidden))
  (cond
    (*lyr:kw_manual*
     (setq *lyr:sel_names* new-all))
    ((null new-all)
     (setq *lyr:sel_names* '()
           *lyr:before* "")
     (set_tile "before_name" ""))
    ((not (= (setq common (lyr:common-substr new-all)) ""))
     (setq *lyr:sel_names* new-all
           *lyr:before* common)
     (set_tile "before_name" common))
    ((not (= *lyr:before* ""))
     ;; 보호: 이전 선택 복원 (set_tile 이 재귀를 유발할 수 있어 플래그로 막음)
     (set_tile "layer_list"
       (lyr:idx->str (lyr:names->idx *lyr:sel_names* *lyr:filtered*))))
    (T
     (setq *lyr:sel_names* new-all
           *lyr:before* "")
     (set_tile "before_name" ""))
  )
  (lyr:update-count)
  (setq *lyr:in-select* nil)
)

;;;─── 필터 이벤트 처리 ────────────────────────────────────────
(defun lyr:on-filter (kw / restore-idx)
  (setq *lyr:filter_kw* kw
        *lyr:filtered*  (lyr:filter kw *lyr:all*))
  (lyr:refresh-list *lyr:filtered*)
  (setq restore-idx (lyr:names->idx *lyr:sel_names* *lyr:filtered*))
  (set_tile "layer_list" (lyr:idx->str restore-idx))
  (lyr:update-count)
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
      "    : text { label = \"레이어 필터 :\"; width = 11; fixed_width = true; }"
      "    : edit_box { key = \"filter_name\"; edit_width = 28; }"
      "    : button { key = \"btn_apply\";    label = \"적용\";     width = 8;  fixed_width = true; }"
      "    : button { key = \"btn_selall\";   label = \"전체선택\"; width = 10; fixed_width = true; }"
      "    : button { key = \"btn_selclear\"; label = \"전체해제\"; width = 10; fixed_width = true; }"
      "  }"
      "  : text { label = \"레이어 목록  (Ctrl/Shift: 다중선택  |  필터: Enter/Tab/적용버튼)\"; }"
      "  : list_box {"
      "    key             = \"layer_list\";"
      "    height          = 20;"
      "    width           = 62;"
      "    multiple_select = true;"
      "  }"
      "  : row {"
      "    : boxed_column {"
      "      label = \"선택 현황\";"
      "      : text {"
      "        key   = \"sel_count\";"
      "        label = \"0 개 선택됨\";"
      "        width = 18;"
      "        alignment = centered;"
      "      }"
      "    }"
      "    : spacer {}"
      "    : button { key = \"btn_convert\"; label = \"  변  환  \"; width = 14; is_default = true; }"
      "    : spacer_0 {}"
      "    : button { key = \"cancel\";      label = \"  취  소  \"; width = 14; is_cancel  = true; }"
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
      "    : button { key = \"accept\"; label = \"  변환 실행  \"; is_default = true; width = 16; }"
      "    : spacer {}"
      "    : button { key = \"cancel\"; label = \"  취  소  \";   is_cancel  = true; width = 16; }"
      "  }"
      "}"
    )
    (write-line s fp)
  )
  (close fp)
)

;;;─── 확인 다이얼로그 ─────────────────────────────────────────
(defun lyr:show-confirm (dcl_id items warn-msg)
  (if (not (new_dialog "confirm_dlg" dcl_id))
    (progn (alert "확인 다이얼로그를 열 수 없습니다.") nil)
    (progn
      (set_tile "confirm_warn" warn-msg)
      (start_list "confirm_list" 3)
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

  ;; 전역 초기화
  (setq *lyr:all*       (lyr:get-all)
        *lyr:filtered*  *lyr:all*
        *lyr:sel_names* '()
        *lyr:before*    ""
        *lyr:after*     ""
        *lyr:kw_manual* nil
        *lyr:filter_kw* ""
        *lyr:in-select* nil)           ; 선택 이벤트 재진입 방지 플래그

  ;; DCL 생성 & 로드
  (setq dcl_file (strcat (getvar "TEMPPREFIX") "lyrename_tmp.dcl"))
  (lyr:write-dcl dcl_file)
  (setq dcl_id (load_dialog dcl_file))
  (if (not (new_dialog "layer_rename" dcl_id))
    (progn (alert "다이얼로그를 열 수 없습니다.") (exit))
  )

  ;; 초기 상태: 전체 레이어 표시
  (lyr:refresh-list *lyr:all*)
  (set_tile "sel_count" "0 개 선택됨")
  (mode_tile "before_name" 2)          ; 커서를 [변경 전] 입력란에 초기 포커스

  ;; ── 타일 이벤트 ───────────────────────────────────────────

  ;; [변경 전] - 직접 입력 시 수동 모드, 지우면 자동 모드로 복귀
  (action_tile "before_name"
    "(progn
       (setq *lyr:before* $value)
       (setq *lyr:kw_manual* (not (= *lyr:before* \"\"))))"
  )

  ;; [변경 후]
  (action_tile "after_name"
    "(setq *lyr:after* $value)"
  )

  ;; [레이어 필터] - Enter / Tab 으로 적용
  (action_tile "filter_name"
    "(lyr:on-filter $value)"
  )

  ;; [적용] 버튼 - 필터 즉시 적용
  (action_tile "btn_apply"
    "(lyr:on-filter (get_tile \"filter_name\"))"
  )

  ;; [전체선택] 버튼 - 현재 필터된 모든 레이어 선택에 추가
  (action_tile "btn_selall"
    "(progn
       (setq *lyr:sel_names* (lyr:union *lyr:sel_names* *lyr:filtered*))
       (set_tile \"layer_list\"
         (lyr:idx->str (lyr:names->idx *lyr:sel_names* *lyr:filtered*)))
       (if (not *lyr:kw_manual*)
         (progn
           (setq *lyr:before* (lyr:common-substr *lyr:sel_names*))
           (set_tile \"before_name\" *lyr:before*)))
       (lyr:update-count))"
  )

  ;; [전체해제] 버튼 - 모든 선택 해제 (자동 모드 복귀 포함)
  (action_tile "btn_selclear"
    "(progn
       (setq *lyr:sel_names* '())
       (if (not *lyr:kw_manual*)
         (progn
           (setq *lyr:before* \"\")
           (set_tile \"before_name\" \"\")))
       (set_tile \"layer_list\" \"\")
       (lyr:update-count))"
  )

  ;; 리스트 선택 변경
  (action_tile "layer_list"
    "(lyr:on-select $value)"
  )

  ;; [변환] 버튼
  ;; 선택이 없으면 현재 목록 전체를 대상으로 자동 지정
  (action_tile "btn_convert"
    "(cond
       ((= *lyr:before* \"\")
        (set_tile \"error\"
          \"[변경 전] 키워드를 입력하세요.\"))
       ((null *lyr:filtered*)
        (set_tile \"error\"
          \"대상 레이어가 없습니다.\"))
       (T
        (if (null *lyr:sel_names*)
          (setq *lyr:sel_names* *lyr:filtered*))
        (done_dialog 1)))"
  )

  (action_tile "cancel" "(done_dialog 0)")

  (setq ret (start_dialog))

  ;; ── 변환 처리 ─────────────────────────────────────────────
  (if (= ret 1)
    (progn
      (setq confirm-items '()
            need-warn     nil)
      (foreach lyr-n *lyr:sel_names*
        (setq new-n  (lyr:replace-all *lyr:before* *lyr:after* lyr-n)
              occur  (lyr:count-occur *lyr:before* lyr-n))
        (setq label
          (cond
            ((= occur 0)
             (setq need-warn T)
             (strcat "  [키워드 없음] " lyr-n "  (변경 안됨)"))
            ((> occur 1)
             (setq need-warn T)
             (strcat "  [" (itoa occur) "회 포함]  " lyr-n "  ->  " new-n))
            (T
             (strcat "  " lyr-n "  ->  " new-n))
          )
        )
        (setq confirm-items (append confirm-items (list label)))
      )
      (setq warn-msg
        (if need-warn
          "[!] 경고 항목이 포함되어 있습니다. 계속 진행하시겠습니까?"
          (strcat (itoa (length *lyr:sel_names*))
                  " 개 레이어를 변환합니다. 내용을 확인하세요.")
        )
      )
      (if (lyr:show-confirm dcl_id confirm-items warn-msg)
        (progn
          (setq cnt 0 errs "")
          (foreach lyr-n *lyr:sel_names*
            (setq old-n lyr-n
                  new-n (lyr:replace-all *lyr:before* *lyr:after* old-n)
                  occur (lyr:count-occur *lyr:before* old-n))
            (cond
              ((= occur 0) nil)
              ((equal old-n new-n) nil)
              ((tblsearch "LAYER" new-n)
               (setq errs (strcat errs "\n  " old-n " -> " new-n "  (이름 충돌)")))
              (T
               (vl-cmdf "-LAYER" "RENAME" old-n new-n "")
               (setq cnt (1+ cnt)))
            )
          )
          (setq msg (strcat (itoa cnt) " 개 레이어 이름이 변경되었습니다."))
          (if (not (= errs ""))
            (setq msg (strcat msg "\n\n[오류]" errs)))
          (alert msg)
        )
        (princ "\n변환이 취소되었습니다.")
      )
    )
  )

  (unload_dialog dcl_id)
  (princ)
)

(princ "\n>> 명령어 [LYRENAME] 으로 레이어 이름 변경 유틸리티를 실행합니다.")
(princ)
