(defun C:MX100 (/ ss i ent obj)
  (vl-load-com)
  (setq ss (ssget "_I"))
  (if (null ss) (setq ss (ssget)))
  (if ss
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq obj (vlax-ename->vla-object (ssname ss i)))
        (vla-Move obj
          (vlax-3d-point '(0 0 0))
          (vlax-3d-point '(100 0 0)))
        (setq i (1+ i))
      )
      (sssetfirst nil ss)
    )
  )
  (princ)
)