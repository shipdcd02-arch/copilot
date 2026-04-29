import os
from collections import Counter
from pathlib import Path

target = input("폴더 경로: ").strip().strip('"').strip("'")
base = Path(target)

if not base.is_dir():
    print("유효한 폴더 경로가 아닙니다.")
    exit(1)

exts = Counter()
for root, dirs, files in os.walk(base):
    for f in files:
        ext = Path(f).suffix.lower()
        exts[ext if ext else "(확장자 없음)"] += 1

print(f"\n총 {sum(exts.values())}개 파일\n")
for ext, cnt in exts.most_common():
    print(f"{ext:>16} : {cnt}개")
