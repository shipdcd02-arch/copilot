abs_path = os.path.abspath(file_path)
    ppt_app = None
    
    try:
        # 1. DispatchEx를 사용하여 독립적인 프로세스 생성
        ppt_app = win32com.client.DispatchEx("PowerPoint.Application")
        
        # 2. 백그라운드 유지를 위해 Window를 만들지 않고 오픈
        # WithWindow=0 (False) 가 핵심입니다.
        presentation = ppt_app.Presentations.Open(abs_path, ReadOnly=True, WithWindow=0)
        
        print(f"독립 프로세스 실행 중: {presentation.Name}")

        for i, slide in enumerate(presentation.Slides):
            print(f"\n--- Slide {i+1} ---")
            for shape in slide.Shapes:
                if shape.HasTextFrame and shape.TextFrame.HasText:
                    raw_text = shape.TextFrame.TextRange.Text
                    
                    # 3. _x000D_ 및 기타 인코딩 찌꺼기 정제
                    clean_text = raw_text.replace("_x000D_", "\n").replace("\r", "\n")
                    print(clean_text)
        
        presentation.Close()
        
    except Exception as e:
        print(f"오류 발생: {e}")
        
    finally:
        # 4. 생성한 독립 프로세스만 종료 (기존 실행 중인 PPT는 영향 없음)
        if ppt_app:
            ppt_app.Quit()
            # COM 객체 메모리 해제 권장
            del ppt_app