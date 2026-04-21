(defun C:MX100 ()
  (setq ss (ssget "_I"))
  (if (null ss)
    (setq ss (ssget)))
  (if ss
    (command "._MOVE" ss "" "0,0,0" "100,0,0"))
  (princ)
)