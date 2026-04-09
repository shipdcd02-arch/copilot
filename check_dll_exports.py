"""
DLL 내보내기 함수 목록 확인 도구
사용법: python check_dll_exports.py
"""
import ctypes
import ctypes.wintypes
import struct
import sys

def get_dll_exports(dll_path):
    try:
        # DLL 파일을 바이너리로 읽어서 PE 헤더 파싱
        with open(dll_path, "rb") as f:
            data = f.read()

        # DOS 헤더에서 PE 헤더 오프셋
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
        pe_offset = e_lfanew

        # 시그니처 확인
        sig = data[pe_offset:pe_offset+4]
        if sig != b"PE\x00\x00":
            print("PE 파일이 아닙니다.")
            return []

        # Optional Header 오프셋
        machine = struct.unpack_from("<H", data, pe_offset + 4)[0]
        is_64bit = (machine == 0x8664)
        opt_offset = pe_offset + 24

        # Export Directory RVA
        if is_64bit:
            export_rva = struct.unpack_from("<I", data, opt_offset + 112)[0]
        else:
            export_rva = struct.unpack_from("<I", data, opt_offset + 96)[0]

        if export_rva == 0:
            print("Export 테이블이 없습니다.")
            return []

        # 섹션 헤더에서 RVA → 파일 오프셋 변환
        num_sections = struct.unpack_from("<H", data, pe_offset + 6)[0]
        section_offset = opt_offset + (240 if is_64bit else 224)

        def rva_to_offset(rva):
            for i in range(num_sections):
                s = section_offset + i * 40
                vaddr = struct.unpack_from("<I", data, s + 12)[0]
                vsize = struct.unpack_from("<I", data, s + 16)[0]
                raw   = struct.unpack_from("<I", data, s + 20)[0]
                if vaddr <= rva < vaddr + vsize:
                    return raw + (rva - vaddr)
            return None

        exp_off = rva_to_offset(export_rva)
        if exp_off is None:
            print("Export 테이블 오프셋 변환 실패")
            return []

        num_names     = struct.unpack_from("<I", data, exp_off + 24)[0]
        names_rva     = struct.unpack_from("<I", data, exp_off + 32)[0]
        names_off     = rva_to_offset(names_rva)

        functions = []
        for i in range(num_names):
            name_rva = struct.unpack_from("<I", data, names_off + i * 4)[0]
            name_off = rva_to_offset(name_rva)
            if name_off is None:
                continue
            end = data.index(b"\x00", name_off)
            name = data[name_off:end].decode("ascii", errors="replace")
            functions.append(name)

        return sorted(functions)

    except Exception as e:
        print(f"오류: {e}")
        return []


if __name__ == "__main__":
    dll_path = input("DLL 전체 경로를 입력하세요: ").strip().strip('"')
    print(f"\n분석 중: {dll_path}\n")

    exports = get_dll_exports(dll_path)

    if exports:
        print(f"총 {len(exports)}개 함수 발견:\n")
        for fn in exports:
            print(f"  {fn}")
    else:
        print("함수를 찾지 못했습니다.")

    input("\n엔터를 누르면 종료...")
