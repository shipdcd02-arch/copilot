@echo off
chcp 65001 > nul
setlocal

:: ─────────────────────────────────────────────────
::  AutoCAD 2018 .NET 플러그인 빌드 스크립트
:: ─────────────────────────────────────────────────
set ACAD_DIR=C:\Program Files\Autodesk\AutoCAD 2018
set BUILD_CONFIG=Release
set OUTPUT_DIR=%~dp0bin\%BUILD_CONFIG%\net47

echo.
echo ============================================
echo  InterferenceCheck 빌드 시작
echo  AutoCAD 경로: %ACAD_DIR%
echo  구성: %BUILD_CONFIG%
echo ============================================
echo.

:: AutoCAD DLL 존재 확인
if not exist "%ACAD_DIR%\AcDbMgd.dll" (
    echo [오류] AutoCAD DLL을 찾을 수 없습니다.
    echo        경로: %ACAD_DIR%
    echo        build.bat 상단의 ACAD_DIR 을 실제 설치 경로로 수정하세요.
    goto END
)
echo [확인] AutoCAD DLL 발견: %ACAD_DIR%

:: dotnet SDK 확인
where dotnet > nul 2>&1
if errorlevel 1 (
    echo [오류] dotnet SDK 가 설치되어 있지 않습니다.
    echo        https://dotnet.microsoft.com/download 에서 설치하세요.
    goto END
)

:: 빌드
echo.
echo [빌드 중...]
dotnet build "%~dp0InterferenceCheck.csproj" ^
    -c %BUILD_CONFIG% ^
    /p:AcadDir="%ACAD_DIR%" ^
    /p:TargetFramework=net47

if errorlevel 1 (
    echo.
    echo [실패] 빌드 오류가 발생했습니다.
    goto END
)

echo.
echo ============================================
echo  빌드 성공!
echo  출력 파일: %OUTPUT_DIR%\InterferenceCheck.dll
echo ============================================
echo.
echo AutoCAD 에서 로드하려면:
echo   명령어: NETLOAD
echo   파일:   %OUTPUT_DIR%\InterferenceCheck.dll
echo   이후 명령어: INTERCHECK
echo.

:END
endlocal
pause
