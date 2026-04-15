;;; ============================================================
;;;  LYRENAME.LSP  -  레이어 이름 일괄 변경 유틸리티
;;;  로드 후 명령어: LYRENAME
;;; ============================================================
(vl-load-com)

;; ── 전체 레이어 이름 목록 반환 (알파벳 정렬) ─────────────────
(defun lyr:get-all (/ lyr acc)
  (setq acc '())
  (setq lyr (tblnext "LAYER" T))
  (while lyr
    (setq acc (cons (cdr (assoc 2 lyr)) acc))
    (setq lyr (tblnext "LAYER"))
  )
  (vl-sort acc '(lambda (a b) (< (strcase a) (strcase b))))
)

;; ── 키워드가 포함된 레이어만 필터링 (대소문자 무시) ──────────
(defun lyr:filter (kw lst)
  (if (= kw "")
    lst
    (vl-remove-if-not
      '(lambda (n)
         (wcmatch (strcase n) (strcat "*" (strcase kw) "*"))
       )
      lst
    )
  )
)

;; ── 문자열에서 old 를 new 로 전체 치환 (대소문자 무시 검색) ──
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

;; ── 선택 인덱스 문자열 "0 2 5" -> 정수 리스트 (0 2 5) ────────
(defun lyr:parse-sel (str / v)
  (if (or (null str) (= str ""))
    '()
    (progn
      (setq v (read (strcat "(" str ")")))
      (if (listp v) v (list v))
    )
  )
)

;; ── 리스트박스 내용 갱신 ──────────────────────────────────────
(defun lyr:refresh-list (lst)
  (start_list "layer_list" 2)
  (if lst (mapcar 'add_list lst))
  (end_list)
)

;; ── DCL 파일을 임시 경로에 생성 ──────────────────────────────
(defun lyr:write-dcl (fpath / fp)
  (setq fp (open fpath "w"))
  (foreach s
    (list
      "layer_rename : dialog {"
      "  label = \"레이어 이름 변경 유틸리티\";"
      "  : boxed_row {"
      "    label = \"검색 / 변경 설정\";"
      "    : column {"
      "      : text { label = \"변경 전  (포함 키워드):\"; }"
      "      : edit_box { key = \"before_name\"; edit_width = 24; }"
      "    }"
      "    : column {"
      "      : text { label = \"변경 후  (교체 텍스트):\"; }"
      "      : edit_box { key = \"after_name\"; edit_width = 24; }"
      "    }"
      "    : column {"
      "      : text { label = \" \"; }"
      "      : button {"
      "        key = \"btn_search\";"
      "        label = \"  검색  \";"
      "        width = 10;"
      "        fixed_width = true;"
      "      }"
      "    }"
      "  }"
      "  : text {"
      "    label = \"검색된 레이어 목록  (Ctrl / Shift 로 다중 선택)\";"
      "  }"
      "  : list_box {"
      "    key             = \"layer_list\";"
      "    height          = 14;"
      "    width           = 62;"
      "    multiple_select = true;"
      "  }"
      "  : row {"
      "    : text {"
      "      key   = \"sel_count\";"
      "      label = \"선택: 0 개\";"
      "      width = 35;"
      "    }"
      "    : spacer {}"
      "  }"
      "  : row {"
      "    : button {"
      "      key        = \"btn_convert\";"
      "      label      = \"  변  환  \";"
      "      width      = 14;"
      "      is_default = true;"
      "    }"
      "    : spacer {}"
      "    : button {"
      "      key       = \"cancel\";"
      "      label     = \"  취  소  \";"
      "      width     = 14;"
      "      is_cancel = true;"
      "    }"
      "  }"
      "  errtile;"
      "}"
    )
    (write-line s fp)
  )
  (close fp)
)

;;; ── 메인 명령 ─────────────────────────────────────────────────
(defun c:LYRENAME (/ dcl_file dcl_id ret cnt old-n new-n errs msg)

  ;; 전역 상태 초기화
  (setq *lyr:all*      (lyr:get-all)
        *lyr:filtered* '()
        *lyr:sel*      '()
        *lyr:before*   ""
        *lyr:after*    "")

  ;; DCL 파일 생성 후 로드
  (setq dcl_file (strcat (getvar "TEMPPREFIX") "lyrename_tmp.dcl"))
  (lyr:write-dcl dcl_file)
  (setq dcl_id (load_dialog dcl_file))

  (if (not (new_dialog "layer_rename" dcl_id))
    (progn (alert "다이얼로그를 열 수 없습니다.") (exit))
  )

  ;; 초기 상태
  (lyr:refresh-list '())
  (set_tile "sel_count" "선택: 0 개")

  ;; ── 타일 이벤트 ──────────────────────────────────────────────

  ;; [변경 전] 입력란 - 포커스 이탈 시 자동 검색
  (action_tile "before_name"
    "(progn
       (setq *lyr:before*   $value
             *lyr:filtered* (lyr:filter *lyr:before* *lyr:all*)
             *lyr:sel*      (quote ()))
       (lyr:refresh-list *lyr:filtered*)
       (set_tile \"sel_count\" \"선택: 0 개\")
       (set_tile \"error\" \"\"))"
  )

  ;; [검색] 버튼 - 수동 재검색
  (action_tile "btn_search"
    "(progn
       (setq *lyr:filtered* (lyr:filter *lyr:before* *lyr:all*)
             *lyr:sel*      (quote ()))
       (lyr:refresh-list *lyr:filtered*)
       (set_tile \"sel_count\" \"선택: 0 개\")
       (set_tile \"error\" \"\"))"
  )

  ;; [변경 후] 입력란
  (action_tile "after_name"
    "(setq *lyr:after* $value)"
  )

  ;; 리스트 선택 이벤트
  (action_tile "layer_list"
    "(progn
       (setq *lyr:sel* (lyr:parse-sel $value))
       (set_tile \"sel_count\"
         (strcat \"선택: \" (itoa (length *lyr:sel*)) \" 개\")))"
  )

  ;; [변환] 버튼 - 유효성 검사 후 확정
  (action_tile "btn_convert"
    "(cond
       ((= *lyr:before* \"\")
        (set_tile \"error\" \"[변경 전] 키워드를 입력하세요.\"))
       ((null *lyr:sel*)
        (set_tile \"error\" \"목록에서 레이어를 하나 이상 선택하세요.\"))
       (T (done_dialog 1)))"
  )

  ;; [취소] 버튼
  (action_tile "cancel" "(done_dialog 0)")

  ;; 다이얼로그 실행
  (setq ret (start_dialog))
  (unload_dialog dcl_id)

  ;; ── 이름 변경 처리 ───────────────────────────────────────────
  (if (= ret 1)
    (progn
      (setq cnt 0  errs "")
      (foreach idx *lyr:sel*
        (setq old-n (nth idx *lyr:filtered*)
              new-n (lyr:replace-all *lyr:before* *lyr:after* old-n))
        (cond
          ;; 치환 결과가 동일하면 스킵
          ((equal old-n new-n)
           nil)
          ;; 같은 이름이 이미 존재하면 오류 기록
          ((tblsearch "LAYER" new-n)
           (setq errs (strcat errs "\n  " old-n " -> " new-n "  (이름 이미 존재)")))
          ;; 정상 변경
          (T
           (vl-cmdf "-LAYER" "RENAME" old-n new-n "")
           (setq cnt (1+ cnt)))
        )
      )
      (setq msg (strcat (itoa cnt) " 개 레이어 이름이 변경되었습니다."))
      (if (not (= errs ""))
        (setq msg (strcat msg "\n\n[변경 실패]" errs))
      )
      (alert msg)
    )
  )

  (princ)
)

(princ "\n>> 명령어 [LYRENAME] 으로 레이어 이름 변경 유틸리티를 실행합니다.")
(princ)
