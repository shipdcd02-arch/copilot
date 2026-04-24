@echo off
setlocal

set ACAD_DIR=C:\Program Files\Autodesk\AutoCAD 2018
set BUILD_CONFIG=Release
set OUTPUT_DIR=%~dp0bin\%BUILD_CONFIG%\net47

echo.
echo ============================================
echo  InterferenceCheck Build
echo  AutoCAD: %ACAD_DIR%
echo  Config : %BUILD_CONFIG%
echo ============================================
echo.

if not exist "%ACAD_DIR%\AcDbMgd.dll" (
    echo [ERROR] AcDbMgd.dll not found at:
    echo         %ACAD_DIR%
    echo  Set ACAD_DIR in build.bat to your AutoCAD install folder.
    goto END
)
echo [OK] AutoCAD DLLs found.

where dotnet >nul 2>&1
if errorlevel 1 (
    echo [ERROR] dotnet SDK not found. Install from https://dotnet.microsoft.com/download
    goto END
)

echo.
echo [Building...]
echo.

dotnet build "%~dp0InterferenceCheck.csproj" -c %BUILD_CONFIG% /p:AcadDir="%ACAD_DIR%" /p:TargetFramework=net47

if errorlevel 1 (
    echo.
    echo [FAILED] Build error.
    goto END
)

echo.
echo ============================================
echo  Build SUCCESS
echo  Output: %OUTPUT_DIR%\InterferenceCheck.dll
echo ============================================
echo.
echo  AutoCAD: NETLOAD - select InterferenceCheck.dll
echo  Command: INTERCHECK
echo.

:END
endlocal
pause
