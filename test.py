(defun c:tt (/ dcl_file f dcl_id data_list item name qty price formatted_item)
  
  ;; 1. 임시 DCL 파일 경로 설정 (현재 도면 폴더에 생성)
  (setq dcl_file (strcat (getvar "dwgprefix") "temp_list.dcl"))

  ;; 2. DCL 파일 쓰기 (내용 직접 생성)
  (setq f (open dcl_file "w"))
  (write-line "temp_dialog : dialog {" f)
  (write-line "    label = \"통합형 리스트박스 예제\";" f)
  (write-line "    : list_box {" f)
  (write-line "        label = \"품목명              |  수량  |  가격\";" f)
  (write-line "        key = \"list_data\";" f)
  (write-line "        width = 50;" f)
  (write-line "        height = 15;" f)
  (write-line "        fixed_width_font = true;" f) // 자릿수 맞춤 핵심
  (write-line "    }" f)
  (write-line "    spacer;" f)
  (write-line "    ok_only;" f)
  (write-line "}" f)
  (close f)

  ;; --- 내부 함수: 실제 가시적 폭 계산 (한글 2칸, 영문 1칸) ---
  (defun get_full_width (str / len i char asc)
    (setq len 0 i 1)
    (repeat (strlen str)
      (setq char (substr str i 1))
      (setq asc (ascii char))
      (if (> asc 128) (setq len (+ len 2)) (setq len (+ len 1)))
      (setq i (1+ i))
    )
    len
  )

  ;; --- 내부 함수: 자릿수 채우기 ---
  (defun pad_str (str target_len / cur_len)
    (setq cur_len (get_full_width str))
    (while (< cur_len target_len)
      (setq str (strcat str " "))
      (setq cur_len (1+ cur_len))
    )
    str
  )

  ;; 3. 데이터 준비
  (setq data_list (list 
    '("Apple" "10" "1,000")
    '("한글 사과" "5" "2,500")
    '("AutoCAD 2026" "1" "50,000")
    '("철근 D10" "150" "12,000")
  ))

  ;; 4. DCL 로드 및 실행
  (setq dcl_id (load_dialog dcl_file))
  (if (not (new_dialog "temp_dialog" dcl_id)) (exit))

  (start_list "list_data")
  (foreach item data_list
    (setq name  (nth 0 item)
          qty   (nth 1 item)
          price (nth 2 item))
    (setq formatted_item (strcat (pad_str name 20) "| " (pad_str qty 6) " | " price))
    (add_list formatted_item)
  )
  (end_list)

  (start_dialog)
  (unload_dialog dcl_id)

  ;; 5. 사용이 끝난 임시 DCL 파일 삭제
  (if (findfile dcl_file) (vl-file-delete dcl_file))

  (princ)
)
(princ "\n명령어 'tt'를 입력하세요.")
(princ)