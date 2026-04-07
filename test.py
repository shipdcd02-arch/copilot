subprocess.Popen(
    [exe_path, tmp_path],
    stdin=subprocess.DEVNULL,       # 없는 핸들 대신 /dev/null 연결
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW,  # 콘솔 창 없이 실행
)
