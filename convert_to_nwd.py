"""
Navisworks FiletoolsTaskRunner를 이용한 DWG/SAT/DGN → NWD 일괄 변환 스크립트
- XML 태스크 파일 방식 사용 (올바른 FiletoolsTaskRunner 호출 방식)
- 실제 출력 파일 존재 여부로 성공 판정
"""

import os
import subprocess
import glob
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

# ──────────────────────────────────────────────
# 설정 영역 (필요에 따라 수정)
# ──────────────────────────────────────────────

# 변환할 파일이 있는 입력 폴더
INPUT_FOLDER = r"C:\입력폴더경로"

# 변환된 NWD 파일을 저장할 출력 폴더 (None 이면 입력 파일과 같은 폴더에 저장)
OUTPUT_FOLDER = r"C:\출력폴더경로"  # 또는 None

# 변환 대상 확장자
TARGET_EXTENSIONS = [".dwg", ".sat", ".dgn"]

# 하위 폴더까지 재귀 검색 여부
RECURSIVE = True

# 파일당 변환 제한 시간 (초)
TIMEOUT = 300

# ──────────────────────────────────────────────


def find_filetools_runner() -> str:
    """설치된 Navisworks의 FiletoolsTaskRunner.exe 경로를 자동 탐색"""
    candidates = []
    for drive in ["C:", "D:", "E:"]:
        pattern = f"{drive}\\Program Files\\Autodesk\\Navisworks*\\FiletoolsTaskRunner.exe"
        candidates.extend(glob.glob(pattern))

    if not candidates:
        return None

    # 가장 최신 버전(경로 기준 내림차순) 선택
    candidates.sort(reverse=True)
    print(f"[탐색된 Navisworks 도구]")
    for c in candidates:
        print(f"  {c}")
    print(f"[사용] {candidates[0]}\n")
    return candidates[0]


def collect_files(input_folder: str, extensions: list, recursive: bool) -> list:
    """지정 폴더에서 변환 대상 파일 목록 수집"""
    files = []
    folder = Path(input_folder)

    if not folder.exists():
        print(f"[오류] 입력 폴더가 존재하지 않습니다: {input_folder}")
        sys.exit(1)

    pattern = "**/*" if recursive else "*"
    for ext in extensions:
        files.extend(folder.glob(f"{pattern}{ext}"))
        files.extend(folder.glob(f"{pattern}{ext.upper()}"))

    return sorted(set(files))


def get_output_path(input_file: Path, output_folder) -> Path:
    """출력 NWD 파일 경로 결정"""
    nwd_name = input_file.stem + ".nwd"
    if output_folder:
        out_dir = Path(output_folder)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / nwd_name
    return input_file.parent / nwd_name


def make_task_xml(input_file: Path, output_file: Path) -> str:
    """FiletoolsTaskRunner용 XML 태스크 파일 생성, 경로 반환"""
    # XML 구조: <tasklist><task type="nwd"><in>...</in><out>...</out></task></tasklist>
    root = ET.Element("tasklist")
    task = ET.SubElement(root, "task", type="nwd")
    ET.SubElement(task, "in").text = str(input_file)
    ET.SubElement(task, "out").text = str(output_file)

    tree = ET.ElementTree(root)
    tmp = tempfile.NamedTemporaryFile(
        suffix=".xml", delete=False, mode="w", encoding="utf-8"
    )
    tmp.write('<?xml version="1.0" encoding="utf-8"?>\n')
    tmp.write(ET.tostring(root, encoding="unicode"))
    tmp.close()
    return tmp.name


def convert_file(runner: str, input_file: Path, output_file: Path) -> bool:
    """단일 파일을 XML 태스크 방식으로 변환"""
    task_xml = make_task_xml(input_file, output_file)

    try:
        cmd = [runner, task_xml]
        print(f"  CMD : {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )

        # stdout/stderr 전체 출력 (디버깅용)
        if result.stdout.strip():
            print(f"  STDOUT: {result.stdout.strip()}")
        if result.stderr.strip():
            print(f"  STDERR: {result.stderr.strip()}")
        print(f"  returncode: {result.returncode}")

        # 실제 파일 생성 여부로 최종 판정
        if output_file.exists():
            size_kb = output_file.stat().st_size // 1024
            print(f"  [성공] {output_file.name}  ({size_kb} KB)")
            return True
        else:
            print(f"  [실패] 출력 파일이 생성되지 않았습니다: {output_file}")
            return False

    except subprocess.TimeoutExpired:
        print(f"  [실패] 시간 초과 ({TIMEOUT}초)")
        return False
    except Exception as e:
        print(f"  [실패] {e}")
        return False
    finally:
        os.unlink(task_xml)


def main():
    print("=" * 60)
    print("  Navisworks 일괄 변환 (DWG/SAT/DGN → NWD)")
    print("=" * 60)

    # 1. FiletoolsTaskRunner.exe 탐색
    runner = find_filetools_runner()
    if not runner:
        print("[오류] FiletoolsTaskRunner.exe를 찾을 수 없습니다.")
        print("       Navisworks Manage 또는 Simulate가 설치되어 있는지 확인하세요.")
        sys.exit(1)

    # 2. 변환 대상 파일 수집
    files = collect_files(INPUT_FOLDER, TARGET_EXTENSIONS, RECURSIVE)
    if not files:
        print(f"[정보] 변환할 파일이 없습니다. (폴더: {INPUT_FOLDER})")
        sys.exit(0)

    print(f"[대상] 총 {len(files)}개 파일\n")

    # 3. 변환 실행
    success, fail = 0, 0
    for i, input_file in enumerate(files, 1):
        output_file = get_output_path(input_file, OUTPUT_FOLDER)
        print(f"[{i}/{len(files)}] {input_file.name}")
        if convert_file(runner, input_file, output_file):
            success += 1
        else:
            fail += 1
        print()

    # 4. 결과 요약
    print("=" * 60)
    print(f"  완료:  성공 {success}개  /  실패 {fail}개  /  전체 {len(files)}개")
    print("=" * 60)


if __name__ == "__main__":
    main()
