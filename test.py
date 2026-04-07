import os
import sys
import uuid

ALLOWED_USER = "yoonk"
ALLOWED_MACHINE_ID = 123456789012345  # print(uuid.getnode()) 로 확인

if os.getlogin() != ALLOWED_USER or uuid.getnode() != ALLOWED_MACHINE_ID:
    print("접근 권한이 없습니다.")
    sys.exit(1)
python -c "import uuid; print(uuid.getnode())"
