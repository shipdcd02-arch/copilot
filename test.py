(defun c:RenameLayerAX (old-n new-n / acadObj doc layers layerObj)
  (vl-load-com)
  (setq acadObj (vlax-get-acad-object))
  (setq doc (vla-get-ActiveDocument acadObj))
  (setq layers (vla-get-Layers doc))

  ;; 에러 방지를 위해 해당 레이어가 있는지 확인 후 이름 변경
  (if (not (vl-catch-all-error-p 
             (setq layerObj (vl-catch-all-apply 'vla-item (list layers old-n)))))
      (vla-put-Name layerObj new-n)
      (princ (strcat "\n오류: '" old-n "' 레이어를 찾을 수 없습니다."))
  )
  (princ)
)