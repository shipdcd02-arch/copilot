(defun c:tt (/ dcl_file f dcl_id data_list item name qty price formatted_item kor_w)
  
  ;; --- 설정: 한글 한 글자의 폭 (안 맞으면 2.0 또는 3.0으로 수정해 보세요) ---
  (setq kor_w 2.0) 

  ;; 1. 임시 DCL 파일 생성
  (setq dcl_file (strcat (getvar "tempprefix") "temp_list.dcl"))
  (setq f (open dcl_file "w"))
  (write-line "temp_dialog : dialog { label = \"자릿수 정밀 보정\";" f)
  (write-line "  : list_box { key = \"list_data\"; width = 60; height = 15; fixed_width_font = true; }" f)
  (write-line "  ok_only; }" f)
  (close f)

  ;; 2. 폭 계산 함수 (실수 연산으로 정밀도 향상)
  (defun get_accurate_width (str kor_multi / len i char asc)
    (setq len 0.0 i 1)
    (repeat (strlen str)
      (setq char (substr str i 1))
      (setq asc (ascii char))
      ;; 한글(멀티바이트) 판별
      (if (> asc 128)
        (setq len (+ len kor_multi))
        (setq len (+ len 1.0))
      )
      (setq i (1+ i))
    )
    len
  )

  ;; 3. 자릿수 채우기 함수
  (defun pad_str (str target_len kor_multi / cur_len)
    (setq cur_len (get_accurate_width str kor_multi))
    (while (< cur_len target_len)
      (setq str (strcat str " "))
      (setq cur_len (1+ cur_len))
    )
    str
  )

  ;; 4. 테스트 데이터
  (setq data_list (list 
    '("Apple" "10" "1,000")
    '("가나다라" "5" "2,500")
    '("AutoCAD 2026" "1" "50,000")
    '("강남구 역삼동" "120" "300,000")
    '("ABC 한글 123" "77" "7,700")
  ))

  ;; 5. DCL 실행
  (setq dcl_id (load_dialog dcl_file))
  (if (not (new_dialog "temp_dialog" dcl_id)) (exit))

  (start_list "list_data")
  (foreach item data_list
    (setq name  (nth 0 item)
          qty   (nth 1 item)
          price (nth 2 item))
    ;; 이름은 25칸, 수량은 8칸 확보
    (setq formatted_item (strcat (pad_str name 25 kor_w) "| " (pad_str qty 8 kor_w) " | " price))
    (add_list formatted_item)
  )
  (end_list)

  (start_dialog)
  (unload_dialog dcl_id)
  (vl-file-delete dcl_file)
  (princ)
)