"""
FiletoolsTaskRunner 단일 파일 변환 디버깅 스크립트
"""

import subprocess
import os
from pathlib import Path

FILETOOLS_RUNNER = r"C:\Program Files\Autodesk\Navisworks Simulate 2022\FiletoolsTaskRunner.exe"

# ── 여기만 수정 ─────────────────────────────────
INPUT_FILE  = r"C:\Users\225715\Desktop\sat변환 테스트용\R350P.sat"
OUTPUT_FILE = r"C:\Users\225715\Desktop\sat변환 테스트용\R350P.nwd"
# ────────────────────────────────────────────────

def test():
    inp = Path(INPUT_FILE)
    out = Path(OUTPUT_FILE)

    # 1. 입력 파일 존재 확인
    print(f"[입력 파일 존재] {inp.exists()} → {inp}")
    if not inp.exists():
        print("  입력 파일이 없습니다. 경로를 확인하세요.")
        return

    # 2. shell=True 방식 (경로 공백·한글 문제 우회)
    cmd_str = f'"{FILETOOLS_RUNNER}" /i "{INPUT_FILE}" /of "{OUTPUT_FILE}" /over'
    print(f"\n[CMD] {cmd_str}\n")

    result = subprocess.run(
        cmd_str,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    print(f"returncode : {result.returncode}")
    print(f"STDOUT     :\n{result.stdout}")
    print(f"STDERR     :\n{result.stderr}")

    if out.exists():
        print(f"\n[성공] {out}  ({out.stat().st_size // 1024} KB)")
    else:
        print(f"\n[실패] 파일 미생성: {out}")
        print("\n── 추가 확인 사항 ──")
        print(f"  출력 폴더 존재: {out.parent.exists()}")
        print(f"  출력 폴더 내 파일 목록:")
        for f in out.parent.iterdir():
            print(f"    {f.name}")

if __name__ == "__main__":
    test()
