"""
Navisworks FiletoolsTaskRunner - DWG/SAT/DGN → NWD 일괄 변환
- 라이선스가 없으면 대기 후 자동 재시도
- 경로가 길면 짧은 임시 경로로 복사 후 변환
"""

import subprocess
import shutil
import time
import sys
import os
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────

FILETOOLS_RUNNER = r"C:\Program Files\Autodesk\Navisworks Simulate 2022\FiletoolsTaskRunner.exe"

INPUT_FOLDER  = r"C:\입력폴더경로"
OUTPUT_FOLDER = r"C:\출력폴더경로"   # None 이면 입력 파일과 같은 폴더

TARGET_EXTENSIONS = {".dwg", ".sat", ".dgn"}
RECURSIVE = True

RETRY_INTERVAL_SEC = 60   # 라이선스 없을 때 재시도 대기 시간 (초)
MAX_RETRIES        = 60   # 최대 재시도 횟수 (60회 × 60초 = 최대 1시간 대기)

# 한글/공백 경로 문제 방지를 위해 항상 임시 폴더를 경유해서 변환
TEMP_DIR = r"C:\nw_tmp"

# ──────────────────────────────────────────────

LICENSE_ERROR_CODE = -2146959355
SUBST_DRIVE = "X:"   # 임시 드라이브 문자 (사용 중이면 다른 문자로 변경)


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def subst_create(drive: str, target: str):
    """드라이브 문자를 폴더에 매핑"""
    subst_remove(drive)  # 이미 있으면 제거 후 재생성
    subprocess.run(f"subst {drive} {target}", shell=True, capture_output=True)


def subst_remove(drive: str):
    """드라이브 매핑 해제"""
    subprocess.run(f"subst {drive} /d", shell=True, capture_output=True)



def run_conversion(input_file: Path, output_file: Path) -> str:
    """
    반환값:
      'success'  - 성공
      'license'  - 라이선스 부족 (재시도 필요)
      'fail'     - 기타 실패
    """
    tmp_dir = Path(TEMP_DIR)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # subst로 드라이브 문자 매핑 → 경로를 X:\파일명 수준으로 최소화
        subst_create(SUBST_DRIVE, str(tmp_dir))
        virt_in  = Path(SUBST_DRIVE + "\\" + input_file.name)
        virt_out = Path(SUBST_DRIVE + "\\" + input_file.stem + ".nwd")

        shutil.copy2(input_file, tmp_dir / input_file.name)

        env = os.environ.copy()
        env["TEMP"] = SUBST_DRIVE + "\\"
        env["TMP"]  = SUBST_DRIVE + "\\"

        cmd = [
            FILETOOLS_RUNNER,
            "/i",   str(virt_in),
            "/of",  str(virt_out),
            "/over",
        ]
        print(f"  CMD : {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            cwd=SUBST_DRIVE + "\\",
            env=env,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        print(f"  returncode : {result.returncode}")
        if stdout:
            print(f"  STDOUT     : {stdout}")
        if stderr:
            print(f"  STDERR     : {stderr}")

        # 라이선스 오류 감지
        if str(LICENSE_ERROR_CODE) in stdout or "Failed to startup Navisworks" in stdout:
            return "license"

        # 파일 생성 여부 확인 (실제 tmp 경로로 확인)
        real_out = tmp_dir / (input_file.stem + ".nwd")
        if real_out.exists():
            output_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(real_out), str(output_file))
            (tmp_dir / input_file.name).unlink(missing_ok=True)
            return "success"

        return "fail"

    except Exception as e:
        print(f"  [예외] {e}")
        return "fail"
    finally:
        subst_remove(SUBST_DRIVE)


def convert_with_retry(input_file: Path, output_file: Path) -> bool:
    for attempt in range(1, MAX_RETRIES + 1):
        status = run_conversion(input_file, output_file)

        if status == "success":
            size_kb = output_file.stat().st_size // 1024
            log(f"  [성공] {output_file.name}  ({size_kb} KB)")
            return True

        elif status == "license":
            log(f"  라이선스 사용 중 - {RETRY_INTERVAL_SEC}초 후 재시도 ({attempt}/{MAX_RETRIES})")
            time.sleep(RETRY_INTERVAL_SEC)

        else:
            log(f"  [실패] 변환 오류: {input_file.name}")
            return False

    log(f"  [실패] 최대 재시도 초과: {input_file.name}")
    return False


def collect_files(folder: Path) -> list[Path]:
    pattern = "**/*" if RECURSIVE else "*"
    return sorted({
        f for f in folder.glob(pattern)
        if f.suffix.lower() in TARGET_EXTENSIONS
    })


def get_output_path(input_file: Path) -> Path:
    if OUTPUT_FOLDER:
        out_dir = Path(OUTPUT_FOLDER)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / (input_file.stem + ".nwd")
    return input_file.with_suffix(".nwd")


def main():
    print("=" * 60)
    print("  Navisworks 일괄 변환  (DWG / SAT / DGN → NWD)")
    print(f"  라이선스 대기: 최대 {MAX_RETRIES * RETRY_INTERVAL_SEC // 60}분")
    print("=" * 60)

    input_dir = Path(INPUT_FOLDER)
    if not input_dir.exists():
        print(f"[오류] 입력 폴더 없음: {INPUT_FOLDER}")
        sys.exit(1)

    files = collect_files(input_dir)
    if not files:
        print(f"[정보] 변환할 파일이 없습니다: {INPUT_FOLDER}")
        sys.exit(0)

    log(f"대상 {len(files)}개 파일\n")

    success = fail = 0
    for i, f in enumerate(files, 1):
        out = get_output_path(f)
        log(f"[{i}/{len(files)}] {f.name}  (경로 {len(str(f))}자)")
        if convert_with_retry(f, out):
            success += 1
        else:
            fail += 1
        print()

    # 임시 폴더 정리
    tmp = Path(TEMP_DIR)
    if tmp.exists() and not any(tmp.iterdir()):
        tmp.rmdir()

    print("=" * 60)
    print(f"  성공 {success}  /  실패 {fail}  /  전체 {len(files)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
