"""
Navisworks FiletoolsTaskRunner를 이용한 DWG/SAT/DGN → NWD 일괄 변환 스크립트
"""

import os
import subprocess
import glob
import sys
from pathlib import Path

# ──────────────────────────────────────────────
# 설정 영역 (필요에 따라 수정)
# ──────────────────────────────────────────────

# FiletoolsTaskRunner.exe 경로 (Navisworks 설치 버전에 맞게 수정)
NAVISWORKS_PATHS = [
    r"C:\Program Files\Autodesk\Navisworks Manage 2025\FiletoolsTaskRunner.exe",
    r"C:\Program Files\Autodesk\Navisworks Manage 2024\FiletoolsTaskRunner.exe",
    r"C:\Program Files\Autodesk\Navisworks Manage 2023\FiletoolsTaskRunner.exe",
    r"C:\Program Files\Autodesk\Navisworks Simulate 2025\FiletoolsTaskRunner.exe",
    r"C:\Program Files\Autodesk\Navisworks Simulate 2024\FiletoolsTaskRunner.exe",
    r"C:\Program Files\Autodesk\Navisworks Simulate 2023\FiletoolsTaskRunner.exe",
]

# 변환할 파일이 있는 입력 폴더
INPUT_FOLDER = r"C:\입력폴더경로"

# 변환된 NWD 파일을 저장할 출력 폴더 (None 이면 입력 파일과 같은 폴더에 저장)
OUTPUT_FOLDER = r"C:\출력폴더경로"  # 또는 None

# 변환 대상 확장자
TARGET_EXTENSIONS = [".dwg", ".sat", ".dgn"]

# 하위 폴더까지 재귀 검색 여부
RECURSIVE = True

# ──────────────────────────────────────────────


def find_filetools_runner() -> str:
    """설치된 Navisworks의 FiletoolsTaskRunner.exe 경로를 자동 탐색"""
    for path in NAVISWORKS_PATHS:
        if os.path.isfile(path):
            return path

    # 환경변수나 다른 드라이브에 설치된 경우 추가 탐색
    for drive in ["C:", "D:", "E:"]:
        pattern = f"{drive}\\Program Files\\Autodesk\\Navisworks*\\FiletoolsTaskRunner.exe"
        matches = glob.glob(pattern)
        if matches:
            return matches[0]

    return None


def collect_files(input_folder: str, extensions: list, recursive: bool) -> list:
    """지정 폴더에서 변환 대상 파일 목록 수집"""
    files = []
    folder = Path(input_folder)

    if not folder.exists():
        print(f"[오류] 입력 폴더가 존재하지 않습니다: {input_folder}")
        sys.exit(1)

    pattern = "**/*" if recursive else "*"
    for ext in extensions:
        found = list(folder.glob(f"{pattern}{ext}"))
        found += list(folder.glob(f"{pattern}{ext.upper()}"))
        files.extend(found)

    # 중복 제거 및 정렬
    return sorted(set(files))


def get_output_path(input_file: Path, output_folder: str) -> Path:
    """출력 NWD 파일 경로 결정"""
    nwd_name = input_file.stem + ".nwd"
    if output_folder:
        out_dir = Path(output_folder)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / nwd_name
    else:
        return input_file.parent / nwd_name


def convert_file(runner: str, input_file: Path, output_file: Path) -> bool:
    """단일 파일 변환 실행"""
    cmd = [
        runner,
        "-in", str(input_file),
        "-out", str(output_file),
    ]

    print(f"  변환 중: {input_file.name}  →  {output_file.name}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 파일당 최대 5분
        )
        if result.returncode == 0:
            print(f"  [성공] {output_file}")
            return True
        else:
            print(f"  [실패] returncode={result.returncode}")
            if result.stderr:
                print(f"         {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  [실패] 시간 초과 (300초)")
        return False
    except Exception as e:
        print(f"  [실패] {e}")
        return False


def main():
    print("=" * 60)
    print("  Navisworks 일괄 변환 (DWG/SAT/DGN → NWD)")
    print("=" * 60)

    # 1. FiletoolsTaskRunner.exe 탐색
    runner = find_filetools_runner()
    if not runner:
        print("[오류] FiletoolsTaskRunner.exe를 찾을 수 없습니다.")
        print("       NAVISWORKS_PATHS 목록을 실제 설치 경로로 수정하세요.")
        sys.exit(1)
    print(f"[도구] {runner}\n")

    # 2. 변환 대상 파일 수집
    files = collect_files(INPUT_FOLDER, TARGET_EXTENSIONS, RECURSIVE)
    if not files:
        print(f"[정보] 변환할 파일이 없습니다. (폴더: {INPUT_FOLDER})")
        sys.exit(0)

    print(f"[대상] 총 {len(files)}개 파일 발견\n")

    # 3. 변환 실행
    success, fail = 0, 0
    for i, input_file in enumerate(files, 1):
        output_file = get_output_path(input_file, OUTPUT_FOLDER)
        print(f"[{i}/{len(files)}]")
        if convert_file(runner, input_file, output_file):
            success += 1
        else:
            fail += 1
        print()

    # 4. 결과 요약
    print("=" * 60)
    print(f"  완료: 성공 {success}개  /  실패 {fail}개  /  전체 {len(files)}개")
    print("=" * 60)


if __name__ == "__main__":
    main()
