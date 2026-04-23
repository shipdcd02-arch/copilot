"""
Navisworks FiletoolsTaskRunner를 이용한 DWG/SAT/DGN → NWD 일괄 변환 스크립트
"""

import subprocess
from pathlib import Path

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────

FILETOOLS_RUNNER = r"C:\Program Files\Autodesk\Navisworks Simulate 2022\FiletoolsTaskRunner.exe"

INPUT_FOLDER  = r"C:\입력폴더경로"
OUTPUT_FOLDER = r"C:\출력폴더경로"  # None 이면 입력 파일과 같은 폴더

TARGET_EXTENSIONS = {".dwg", ".sat", ".dgn"}
RECURSIVE = True

# ──────────────────────────────────────────────


def convert_to_nwd(input_path: str, output_path: str) -> bool:
    cmd = [
        FILETOOLS_RUNNER,
        "/i", input_path,
        "/of", output_path,
        "/over",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    print(f"  CMD       : {' '.join(cmd)}")
    print(f"  returncode: {result.returncode}")
    if result.stdout.strip():
        print(f"  STDOUT    : {result.stdout.strip()}")
    if result.stderr.strip():
        print(f"  STDERR    : {result.stderr.strip()}")

    out = Path(output_path)
    if out.exists():
        print(f"  [성공] {out.name}  ({out.stat().st_size // 1024} KB)")
        return True
    else:
        print(f"  [실패] 파일 미생성: {output_path}")
        return False


def collect_files(folder: Path) -> list[Path]:
    pattern = "**/*" if RECURSIVE else "*"
    files = [
        f for f in folder.glob(pattern)
        if f.suffix.lower() in TARGET_EXTENSIONS
    ]
    return sorted(files)


def get_output_path(input_file: Path) -> Path:
    if OUTPUT_FOLDER:
        out_dir = Path(OUTPUT_FOLDER)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / (input_file.stem + ".nwd")
    return input_file.with_suffix(".nwd")


def main():
    print("=" * 60)
    print("  Navisworks 일괄 변환 (DWG / SAT / DGN → NWD)")
    print("=" * 60)

    input_dir = Path(INPUT_FOLDER)
    if not input_dir.exists():
        print(f"[오류] 입력 폴더 없음: {INPUT_FOLDER}")
        return

    files = collect_files(input_dir)
    if not files:
        print(f"[정보] 변환할 파일이 없습니다: {INPUT_FOLDER}")
        return

    print(f"[대상] {len(files)}개 파일\n")

    success = fail = 0
    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {f.name}")
        out = get_output_path(f)
        if convert_to_nwd(str(f), str(out)):
            success += 1
        else:
            fail += 1
        print()

    print("=" * 60)
    print(f"  성공 {success}  /  실패 {fail}  /  전체 {len(files)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
