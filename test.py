(defun c:MoveAndClean (/ fso filePath parentDir targetDir fileName fileExt baseName newFileName targetPath count)
  (vl-load-com)
  (setq fso (vlax-create-object "Scripting.FileSystemObject"))

  ;; 1. 사용자로부터 파일 선택 받기
  (setq filePath (getfiled "이동할 파일을 선택하세요" "" "*" 8))
  
  (if (and filePath (vlax-invoke fso 'FileExists filePath))
    (progn
      ;; 파일 정보 추출
      (setq parentDir (vl-filename-directory filePath)) ; 현재 파일이 있는 폴더
      (setq targetDir (vl-filename-directory parentDir)) ; 상위 폴더 (이동할 목적지)
      (setq fileName (vl-filename-base filePath))      ; 파일명 (확장자 제외)
      (setq fileExt  (vl-filename-extension filePath)) ; 확장자 (.dwg 등)

      ;; 2. 파일명 끝의 "_1" 제거 규칙 적용
      (if (equal (substr fileName (- (strlen fileName) 1)) "_1")
        (setq baseName (substr fileName 1 (- (strlen fileName) 2)))
        (setq baseName fileName)
      )

      ;; 3. 중복 파일 체크 및 일련번호(-1, -2...) 생성
      (setq newFileName (strcat baseName fileExt))
      (setq targetPath (strcat targetDir "\\" newFileName))
      (setq count 1)

      (while (vlax-invoke fso 'FileExists targetPath)
        (setq newFileName (strcat baseName "-" (itoa count) fileExt))
        (setq targetPath (strcat targetDir "\\" newFileName))
        (setq count (1+ count))
      )

      ;; 4. 파일 이동 (이름 변경 포함)
      (vl-catch-all-apply 'vlax-invoke (list fso 'MoveFile filePath targetPath))
      (princ (strcat "\n파일이 이동되었습니다: " targetPath))

      ;; 5. 원래 폴더가 비었는지 확인 후 삭제
      (setq oldFolder (vlax-invoke fso 'GetFolder parentDir))
      (if (and (= (vlax-get-property (vlax-get-property oldFolder 'Files) 'Count) 0)
               (= (vlax-get-property (vlax-get-property oldFolder 'SubFolders) 'Count) 0))
        (progn
          (vlax-invoke fso 'DeleteFolder parentDir :vlax-true)
          (princ (strcat "\n빈 폴더가 삭제되었습니다: " parentDir))
        )
        (princ "\n폴더 내에 다른 파일이 남아있어 폴더를 삭제하지 않았습니다.")
      )
    )
    (princ "\n파일 선택이 취소되었거나 파일이 존재하지 않습니다.")
  )

  (vlax-release-object fso)
  (princ)
)

