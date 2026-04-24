@echo off
for /f "tokens=*" %%i in ('powershell -command "Get-Date -Format HHmmss"') do set TS=%%i
dotnet build /p:AssemblyName=SA_%TS%
echo.
echo ================================
echo AutoCAD에서 NETLOAD할 파일:
echo bin\Debug\net47\SA_%TS%.dll
echo ================================
pause