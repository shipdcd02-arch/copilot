; 섹션 플레인 선택 후 사용 가능한 메서드 목록 출력
(defun c:DumpSection ( / ent obj)
  (vl-load-com)
  (setq ent (car (entsel "\n섹션 플레인 선택: ")))
  (setq obj (vlax-ename->vla-object ent))
  (vlax-dump-object obj T)  ; T = 메서드 포함 출력
  (princ)
)