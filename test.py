(defun c:SectionToBlockAX ( / doc sel obj)
  (vl-load-com)
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  ;; 사용자에게 섹션 플레인 선택 요청
  (setq sel (car (entsel "\n섹션 플레인 선택: ")))
  (if sel
    (progn
      (setq obj (vlax-ename->vla-object sel))
      ;; GenerateSectionGeometry 메서드 사용 (버전에 따라 다름)
      (vla-GenerateSectionGeometry obj)
    )
  )
  (princ)
)