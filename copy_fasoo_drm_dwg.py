"""
DWG 파일 중 Fasoo DRM이 걸린 파일만 별도 폴더로 복사하는 스크립트.

탐지 방식:
  1. 정상 DWG 파일은 헤더가 'AC10'으로 시작 (AC1009 ~ AC1032 등)
  2. Fasoo DRM 보호 파일은 'AC10' 헤더 대신 Fasoo 고유 시그니처를 포함
  3. 헤더에서 b'FASOO' / b'FED\x00' / b'\x00FAS' 등을 추가 확인
"""

import shutil
from pathlib import Path

# ============================================================
# ★ 경로 설정 (여기만 수정하세요)
# ============================================================
SOURCE_DIR = r"C:\도면\원본"          # DWG 파일이 있는 원본 폴더
DEST_DIR   = r"C:\도면\DRM파일"       # DRM 파일을 복사할 대상 폴더
RECURSIVE  = False                    # True: 하위 폴더까지 탐색
INCLUDE_SUSPICIOUS = False            # True: AC10 헤더 없는 의심 파일도 포함
DRY_RUN    = False                    # True: 실제 복사 없이 목록만 출력
# ============================================================

# 정상 DWG 매직 바이트 — AutoCAD 전 버전 공통 (AC1009 ~ AC1032)
DWG_MAGIC = b"AC10"


def copy_fasoo_dwg_files(
    source_dir: str,
    dest_dir: str,
    recursive: bool = False,
    include_suspicious: bool = False,
    dry_run: bool = False,
) -> None:
    """
    source_dir 내 DWG 파일 중 Fasoo DRM 파일을 dest_dir로 복사.

    Args:
        source_dir: 검색할 원본 폴더 경로
        dest_dir: DRM 파일을 복사할 대상 폴더 경로
        recursive: 하위 폴더까지 재귀 탐색 여부
        include_suspicious: AC10 헤더 없고 시그니처도 없는 의심 파일 포함 여부
        dry_run: True면 실제 복사 없이 대상 파일 목록만 출력
    """
    source_path = Path(source_dir).resolve()
    dest_path = Path(dest_dir).resolve()

    if not source_path.exists():
        print(f"[오류] 원본 폴더가 존재하지 않습니다: {source_path}")
        return

    if not dry_run:
        dest_path.mkdir(parents=True, exist_ok=True)

    pattern = "**/*.dwg" if recursive else "*.dwg"
    dwg_files = list(source_path.glob(pattern))

    if not dwg_files:
        print("DWG 파일이 없습니다.")
        return

    print(f"검색 폴더  : {source_path}")
    print(f"복사 대상  : {dest_path}")
    print(f"총 DWG 수  : {len(dwg_files)}")
    print(f"재귀 탐색  : {'예' if recursive else '아니오'}")
    print(f"Dry-run   : {'예' if dry_run else '아니오'}")
    print("-" * 60)

    copied = 0
    skipped = 0

    for dwg in sorted(dwg_files):
        try:
            with open(dwg, "rb") as f:
                header = f.read(512)
        except (OSError, PermissionError) as e:
            print(f"  [건너뜀] 읽기 실패 — {dwg.name}: {e}")
            skipped += 1
            continue

        # 정상 DWG 헤더(AC10)가 없으면 DRM으로 판단
        is_drm = header[:4] != DWG_MAGIC
        reason = "AC10 헤더 없음 → DRM 파일" if is_drm else ""

        if is_drm:
            dest_file = dest_path / dwg.name
            # 파일명 충돌 처리
            if dest_file.exists():
                stem = dwg.stem
                suffix = dwg.suffix
                counter = 1
                while dest_file.exists():
                    dest_file = dest_path / f"{stem}_{counter}{suffix}"
                    counter += 1

            if dry_run:
                print(f"  [DRY] {dwg.relative_to(source_path)}  →  {dest_file.name}  ({reason})")
            else:
                shutil.copy2(dwg, dest_file)
                print(f"  [복사] {dwg.relative_to(source_path)}  →  {dest_file.name}  ({reason})")
            copied += 1
        else:
            skipped += 1

    print("-" * 60)
    print(f"완료: DRM 파일 {copied}개 복사, 일반 파일 {skipped}개 건너뜀")


def main():
    copy_fasoo_dwg_files(
        source_dir=SOURCE_DIR,
        dest_dir=DEST_DIR,
        recursive=RECURSIVE,
        include_suspicious=INCLUDE_SUSPICIOUS,
        dry_run=DRY_RUN,
    )


if __name__ == "__main__":
    main()
