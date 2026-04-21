(defun C:MX100 (/ ss i obj gr key)
  (vl-load-com)
  (setq ss (ssget "_I"))
  (if (null ss) (setq ss (ssget)))
  (if ss
    (progn
      (sssetfirst nil ss)
      (princ "\n[Space/Enter: +100mm]  [ESC: 종료]")
      (while
        (progn
          (setq gr (grread nil 2 0))
          (setq key (cadr gr))
          (cond
            ((or (= key 32) (= key 13))
             (setq i 0)
             (while (< i (sslength ss))
               (setq obj (vlax-ename->vla-object (ssname ss i)))
               (vla-Move obj
                 (vlax-3d-point '(0 0 0))
                 (vlax-3d-point '(100 0 0)))
               (setq i (1+ i))
             )
             (sssetfirst nil ss)
             T)
            ((= key 27) nil)
            (T T)
          )
        )
      )
    )
  )
  (princ)
)