"""
DWG 파일의 헤더를 16진수로 출력하는 진단 스크립트.
DRM 파일과 일반 파일을 비교해서 시그니처를 찾을 때 사용합니다.
"""

from pathlib import Path

# ============================================================
# ★ 확인할 폴더 경로 (여기만 수정하세요)
# ============================================================
TARGET_DIR = r"C:\도면\원본"
# ============================================================

BYTES_TO_READ = 256  # 헤더 몇 바이트까지 출력할지


def dump_header(filepath: Path):
    with open(filepath, "rb") as f:
        data = f.read(BYTES_TO_READ)

    print(f"\n{'='*60}")
    print(f"파일: {filepath.name}")
    print(f"크기: {filepath.stat().st_size:,} bytes")
    print(f"첫 4바이트 (텍스트): {data[:4]}")
    print()

    # 16진수 + ASCII 덤프
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        asc_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"  {i:04X}  {hex_part:<48}  {asc_part}")

    # 문자열로 읽을 수 있는 부분 출력
    printable = "".join(chr(b) if 32 <= b < 127 else " " for b in data)
    tokens = [t for t in printable.split() if len(t) >= 3]
    if tokens:
        print(f"\n  [읽을 수 있는 문자열]: {' | '.join(tokens[:20])}")


def main():
    target = Path(TARGET_DIR)
    dwg_files = sorted(target.glob("*.dwg"))[:10]  # 최대 10개만

    if not dwg_files:
        print("DWG 파일이 없습니다.")
        return

    print(f"폴더: {target}")
    print(f"파일 {len(dwg_files)}개 헤더 출력 (최대 10개)")

    for dwg in dwg_files:
        try:
            dump_header(dwg)
        except Exception as e:
            print(f"\n[오류] {dwg.name}: {e}")

    print(f"\n{'='*60}")
    print("위 출력에서 Fasoo DRM 파일의 고유 패턴을 확인하세요.")
    print("정상 DWG는 첫 줄이 'AC10' 으로 시작합니다.")


if __name__ == "__main__":
    main()
