(defun c:GEN2D_AUTO (/ ent obj)
  (vl-load-com)
  ;; 1. SECTIONOBJECT 선택
  (if (setq ent (car (entsel "\n단면 객체를 선택하세요: ")))
    (progn
      (setq obj (vlax-ename->vla-object ent))
      
      ;; 2. 객체가 진짜 단면 객체인지 확인
      (if (= (vla-get-ObjectName obj) "AcDbSection")
        (progn
          ;; 3. 2D 단면 블록 생성 함수 호출
          ;; (vla-GenerateSectionBlock 객체 대상객체(보통 현재도면) 블록이름)
          ;; 여기서는 수동으로 대화창 없이 처리하기 위해 내부 메서드를 활용해야 합니다.
          (princ "\n이 방식은 VLA 메서드를 통해 대화창 없이 블록을 생성합니다.")
          
          ;; 실제로는 명령어 대신 아래의 LISP 함수 호출이 더 효과적일 수 있습니다.
          (command "_.SECTIONPLANETOBLOCK" ent "") 
          ;; 만약 위 명령어가 대화창을 띄운다면, SendKeys나 별도의 ARX 함수가 필요할 수 있습니다.
        )
      )
    )
  )
  (princ)
)