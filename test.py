import subprocess

# 창을 띄우지 않기 위한 설정
startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startupinfo.wShowWindow = 0  # SW_HIDE (창 숨김)

subprocess.run(
    ['cmd', '/c', exe_path, tmp_path], 
    startupinfo=startupinfo,
    creationflags=subprocess.CREATE_NO_WINDOW  # 창 생성 방지 플래그
)