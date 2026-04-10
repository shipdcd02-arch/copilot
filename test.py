import os
import sys
import subprocess

def resolve(path):
    path = os.path.abspath(path).lower()
    drive, tail = os.path.splitdrive(path)
    if not drive or path.startswith('\\\\'):
        return path
    try:
        out = subprocess.run(['net', 'use', drive], capture_output=True, text=True).stdout
        unc = next((t for t in out.split() if t.lower().startswith('\\\\')), None)
        if unc:
            return unc.lower() + tail
    except Exception:
        pass
    return path

ALLOWED = [resolve(p) for p in [
    r'C:\MyApp',
    r'\\fileserver\share\projects\app',
]]

if not any(resolve(os.path.dirname(os.path.abspath(sys.argv[0]))).startswith(p) for p in ALLOWED):
    sys.exit("허용되지 않은 경로입니다.")
