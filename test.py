import win32com.client
import os

def read_ppt_background(file_path):
    # 파일의 절대 경로가 필요합니다.
    abs_path = os.path.abspath(file_path)
    
    try:
        # PowerPoint 애플리케이션 객체 생성
        ppt_app = win32com.client.Dispatch("PowerPoint.Application")
        
        # 백그라운드 실행을 위해 Visible 속성을 False로 설정 (0 또는 False)
        # 단, 일부 환경에서는 Open() 메서드 실행 시 창이 보일 수 있으므로 
        # WithWindow=False 옵션을 함께 사용합니다.
        ppt_app.Visible = True  # COM 구조상 Visible을 먼저 켜야 제어가 가능한 경우가 있음
        
        # 프레젠테이션 열기 (ReadOnly=True, Untitled=False, WithWindow=False)
        # WithWindow=False가 실제 '백그라운드' 핵심 옵션입니다.
        presentation = ppt_app.Presentations.Open(abs_path, ReadOnly=True, WithWindow=False)
        
        print(f"파일명: {presentation.Name}")
        print(f"슬라이드 개수: {presentation.Slides.Count}")
        
        # 예시: 모든 슬라이드의 텍스트 추출
        for i, slide in enumerate(presentation.Slides):
            print(f"\n--- Slide {i+1} ---")
            for shape in slide.Shapes:
                if shape.HasTextFrame:
                    if shape.TextFrame.HasText:
                        print(shape.TextFrame.TextRange.Text)
        
        # 작업 완료 후 프레젠테이션 닫기
        presentation.Close()
        
    except Exception as e:
        print(f"오류 발생: {e}")
        
    finally:
        # 중요: PowerPoint 애플리케이션 완전히 종료
        if 'ppt_app' in locals():
            ppt_app.Quit()

# 실행
read_ppt_background("your_presentation.pptx")