import win32com.client
import pythoncom
import gc
import os
import re

def read_ppt_perfectly(file_path):
    abs_path = os.path.abspath(file_path)
    ppt_app = None
    presentation = None
    
    try:
        ppt_app = win32com.client.DispatchEx("PowerPoint.Application")
        presentation = ppt_app.Presentations.Open(abs_path, ReadOnly=True, WithWindow=0)
        
        for i, slide in enumerate(presentation.Slides):
            print(f"\n--- Slide {i+1} ---")
            for shape in slide.Shapes:
                if shape.HasTextFrame and shape.TextFrame.HasText:
                    text = shape.TextFrame.TextRange.Text
                    text = text.replace("_x000D_", "")
                    text = text.replace("\r", "\n")
                    text = re.sub(r'\n+', '\n', text).strip()
                    if text:
                        print(text)
        
    except Exception as e:
        print(f"오류 발생: {e}")
        
    finally:
        if presentation:
            presentation.Close()
            del presentation
        if ppt_app:
            # Quit() 제거 — 기존 PPT 인스턴스 보호
            del ppt_app
        gc.collect()  # COM 참조 즉시 해제

read_ppt_perfectly("your_presentation.pptx")
