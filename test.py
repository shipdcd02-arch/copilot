import win32com.client
import os
import re

def read_ppt_perfectly(file_path):
    abs_path = os.path.abspath(file_path)
    ppt_app = None
    
    try:
        # 1. 독립 프로세스 생성
        ppt_app = win32com.client.DispatchEx("PowerPoint.Application")
        
        # 2. 파일 열기 (WithWindow=0으로 백그라운드 보장)
        # ReadOnly=True, WithWindow=False
        presentation = ppt_app.Presentations.Open(abs_path, ReadOnly=True, WithWindow=0)
        
        for i, slide in enumerate(presentation.Slides):
            print(f"\n--- Slide {i+1} ---")
            for shape in slide.Shapes:
                if shape.HasTextFrame and shape.TextFrame.HasText:
                    text = shape.TextFrame.TextRange.Text
                    
                    # 3. 이상한 문자 및 빈 줄 처리
                    # _x000D_ 제거
                    text = text.replace("_x000D_", "")
                    
                    # \r\n, \r 등을 모두 \n으로 통일
                    text = text.replace("\r", "\n")
                    
                    # 연속된 줄바꿈(\n\n+)을 하나의 줄바꿈(\n)으로 합치기 (빈 줄 제거)
                    # 만약 문단 사이의 빈 줄은 남기고 싶다면 이 줄은 주석 처리하세요.
                    text = re.sub(r'\n+', '\n', text).strip()
                    
                    if text:
                        print(text)
        
        # 4. 파일만 닫기
        presentation.Close()
        
    except Exception as e:
        print(f"오류 발생: {e}")
        
    finally:
        if ppt_app:
            # 기존 PPT 보호를 위해 Quit() 대신 객체 해제 시도
            # 만약 여전히 꺼진다면 Quit()을 지우고 실행해보세요.
            ppt_app.Quit() 
            import pythoncom
            ppt_app = None
            pythoncom.CoUninitialize()

read_ppt_perfectly("your_presentation.pptx")