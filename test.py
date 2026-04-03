import sys
import os
import winreg
import subprocess
import shutil

# ============================================================
#  설정
# ============================================================
FAS_FILES = [
    r"\\Cnas08\2dda938477b5d4c$\협력사\두올\협력사참조도면\program\KLISP\klisp.fas"
]

# 복사할 PC3 파일 목록
PC3_FILES = [
    r"C:\임시경로\임윤근-DWG to PDF.pc3",  # 수정 필요
]

# 복사할 CTB 파일 목록
CTB_FILES = [
    r"C:\임시경로\임윤근.CTB",  # 수정 필요
]
# ============================================================


def is_acad_running():
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq acad.exe"],
        capture_output=True, text=True
    )
    return "acad.exe" in result.stdout.lower()


def get_acad_versions():
    versions = []
    try:
        base_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Autodesk\AutoCAD")
        i = 0
        while True:
            try:
                ver = winreg.EnumKey(base_key, i)
                ver_key = winreg.OpenKey(base_key, ver)
                j = 0
                while True:
                    try:
                        prod = winreg.EnumKey(ver_key, j)
                        if prod.startswith("ACAD-"):
                            prod_path = rf"Software\Autodesk\AutoCAD\{ver}\{prod}"
                            try:
                                pk = winreg.OpenKey(winreg.HKEY_CURRENT_USER, prod_path)
                                try:
                                    name, _ = winreg.QueryValueEx(pk, "ProductName")
                                except:
                                    name = "AutoCAD (알수없음)"
                                versions.append((name, prod_path))
                                winreg.CloseKey(pk)
                            except:
                                pass
                        j += 1
                    except OSError:
                        break
                winreg.CloseKey(ver_key)
                i += 1
            except OSError:
                break
        winreg.CloseKey(base_key)
    except:
        pass
    return versions


def get_profiles(prod_path):
    profiles = []
    try:
        profiles_path = prod_path + r"\Profiles"
        pk = winreg.OpenKey(winreg.HKEY_CURRENT_USER, profiles_path)
        i = 0
        while True:
            try:
                prof = winreg.EnumKey(pk, i)
                profiles.append(profiles_path + "\\" + prof)
                i += 1
            except OSError:
                break
        winreg.CloseKey(pk)
    except:
        pass
    return profiles


def expand_path(path):
    """레지스트리 경로에 포함된 환경변수 및 특수문자 처리"""
    if not path:
        return path
    # %변수% 형태 확장
    path = os.path.expandvars(path)
    # "." 으로 시작하는 상대경로 처리 (AutoCAD가 .\ 로 저장하는 경우)
    if path.startswith("."):
        return None
    return path


def get_plotters_paths(prod_path):
    """레지스트리에서 Plotters 경로(PC3)와 Plot Styles 경로(CTB) 자동 탐색"""
    plotters_path = None
    plotstyles_path = None

    # --- 방법 1: Profiles\<프로필>\General 에서 탐색 ---
    # 버전별로 키 이름이 다를 수 있으므로 후보 목록으로 시도
    pc3_key_candidates  = ["PrinterConfigDir", "PRINTERCONDIR", "PrinterRootDir"]
    ctb_key_candidates  = ["PrinterStyleSheetDir", "PRINTERSTYLEDIR", "PrinterStyleRoot"]

    try:
        profiles_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, prod_path + r"\Profiles")
        i = 0
        while True:
            try:
                prof = winreg.EnumKey(profiles_key, i)
                general_key_path = prod_path + rf"\Profiles\{prof}\General"
                try:
                    gk = winreg.OpenKey(winreg.HKEY_CURRENT_USER, general_key_path)

                    if not plotters_path:
                        for key_name in pc3_key_candidates:
                            try:
                                val, _ = winreg.QueryValueEx(gk, key_name)
                                val = expand_path(val)
                                if val and os.path.isdir(val):
                                    plotters_path = val
                                    break
                            except:
                                pass

                    if not plotstyles_path:
                        for key_name in ctb_key_candidates:
                            try:
                                val, _ = winreg.QueryValueEx(gk, key_name)
                                val = expand_path(val)
                                if val and os.path.isdir(val):
                                    plotstyles_path = val
                                    break
                            except:
                                pass

                    winreg.CloseKey(gk)
                except:
                    pass
                if plotters_path and plotstyles_path:
                    break
                i += 1
            except OSError:
                break
        winreg.CloseKey(profiles_key)
    except:
        pass

    # --- 방법 2: 레지스트리 못 찾으면 기본 경로 패턴으로 fallback ---
    if not plotters_path or not plotstyles_path:
        appdata = os.environ.get("APPDATA", "")
        # AutoCAD 버전별 기본 경로 패턴
        # ex) C:\Users\xxx\AppData\Roaming\Autodesk\AutoCAD 2024\R24.3\kor\Plotters
        autodesk_root = os.path.join(appdata, "Autodesk")
        if os.path.isdir(autodesk_root):
            for folder in sorted(os.listdir(autodesk_root), reverse=True):
                acad_dir = os.path.join(autodesk_root, folder)
                if not os.path.isdir(acad_dir):
                    continue
                # 하위 버전 폴더 (R24.x 등) 탐색
                for sub in os.listdir(acad_dir):
                    sub_dir = os.path.join(acad_dir, sub)
                    if not os.path.isdir(sub_dir):
                        continue
                    # 언어 폴더 (kor, en-US 등) 탐색
                    for lang in os.listdir(sub_dir):
                        lang_dir = os.path.join(sub_dir, lang)
                        if not os.path.isdir(lang_dir):
                            continue

                        if not plotters_path:
                            candidate = os.path.join(lang_dir, "Plotters")
                            if os.path.isdir(candidate):
                                plotters_path = candidate

                        if not plotstyles_path:
                            candidate = os.path.join(lang_dir, "Plotters", "Plot Styles")
                            if os.path.isdir(candidate):
                                plotstyles_path = candidate

                        if plotters_path and plotstyles_path:
                            break
                    if plotters_path and plotstyles_path:
                        break
                if plotters_path and plotstyles_path:
                    break

    return plotters_path, plotstyles_path


def copy_files(src_files, dest_dir):
    if not dest_dir or not os.path.isdir(dest_dir):
        return 0

    copied = 0
    for src in src_files:
        if not os.path.exists(src):
            continue
        dest = os.path.join(dest_dir, os.path.basename(src))
        if not os.path.exists(dest):
            try:
                shutil.copy2(src, dest)
                copied += 1
            except:
                pass
    return copied


def register_fas(startup_key_path, fas_path):
    try:
        try:
            sk = winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup_key_path, 0, winreg.KEY_ALL_ACCESS)
        except:
            sk = winreg.CreateKey(winreg.HKEY_CURRENT_USER, startup_key_path)

        try:
            num_str, _ = winreg.QueryValueEx(sk, "NumStartup")
            num_startup = int(num_str)
        except:
            num_startup = 0

        for idx in range(num_startup):
            try:
                val, _ = winreg.QueryValueEx(sk, f"{idx+1}Startup")
                if val.lower() == fas_path.lower():
                    winreg.CloseKey(sk)
                    return "already"
            except:
                pass

        next_num = num_startup + 1
        winreg.SetValueEx(sk, f"{next_num}Startup", 0, winreg.REG_SZ, fas_path)
        winreg.SetValueEx(sk, "NumStartup", 0, winreg.REG_SZ, str(next_num))
        winreg.CloseKey(sk)
        return "registered"

    except Exception as e:
        return f"error: {e}"


def main():
    # AutoCAD 실행 중 체크
    if is_acad_running():
        input("  [경고] AutoCAD가 실행 중입니다. 종료 후 엔터를 누르세요...")
        if is_acad_running():
            print("  [오류] AutoCAD가 아직 실행 중입니다. 종료 후 다시 실행하세요.")
            input("\n  엔터를 눌러 종료...")
            sys.exit(1)

    # FAS 파일 존재 확인
    valid_fas = [f for f in FAS_FILES if os.path.exists(f)]
    if not valid_fas:
        input("\n  [오류] 유효한 FAS 파일이 없습니다.\n  엔터를 눌러 종료...")
        sys.exit(1)

    # AutoCAD 버전 스캔
    versions = get_acad_versions()
    if not versions:
        input("\n  [오류] 설치된 AutoCAD를 찾지 못했습니다.\n  엔터를 눌러 종료...")
        sys.exit(1)

    fas_count = 0
    pc3_count = 0
    ctb_count = 0

    for prod_name, prod_path in versions:

        # FAS 등록
        profiles = get_profiles(prod_path)
        for prof_path in profiles:
            startup_key = prof_path + r"\Dialogs\Appload\Startup"
            for fas in valid_fas:
                result = register_fas(startup_key, fas)
                if result == "registered":
                    fas_count += 1

        # PC3 / CTB 복사
        plotters_dir, plotstyles_dir = get_plotters_paths(prod_path)
        pc3_count += copy_files(PC3_FILES, plotters_dir)
        ctb_count += copy_files(CTB_FILES, plotstyles_dir)

    print(f"  완료: AutoCAD {len(versions)}개 감지 / FAS {fas_count}건 등록 / PC3 {pc3_count}건 복사 / CTB {ctb_count}건 복사")
    input("\n  엔터를 눌러 종료...")


if __name__ == "__main__":
    main()
