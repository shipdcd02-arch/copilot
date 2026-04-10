import os
import sys
import winreg

def resolve(path):
    path = os.path.abspath(path).lower()
    if path.startswith('\\\\'):
        return path
    drive, tail = os.path.splitdrive(path)
    if not drive:
        return path
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, f'Network\\{drive[0]}')
        unc, _ = winreg.QueryValueEx(key, 'RemotePath')
        return (unc + tail).lower()
    except Exception:
        return path  # 로컬 드라이브면 그대로

ALLOWED = [resolve(p) for p in [
    r'C:\MyApp',
    r'\\fileserver\share\projects\app',
]]

if not any(resolve(os.path.dirname(os.path.abspath(sys.argv[0]))).startswith(p) for p in ALLOWED):
    sys.exit("허용되지 않은 경로입니다.")
