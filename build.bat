@echo off
setlocal
set VERSION=1.7.0
if exist installer\bundled\MicroSIP.exe python extract_icon.py
if errorlevel 1 exit /b 1
pyinstaller --onefile --windowed --icon=icon.ico --version-file=version_info.txt --name MicroSIPButton main.py
if errorlevel 1 exit /b 1
if not exist dist\MicroSIPButton.exe exit /b 1
set ISCC=D:\Programs\InnoSetup\ISCC.exe
if not exist "%ISCC%" set ISCC=ISCC.exe
"%ISCC%" /DAppVersion=%VERSION% installer\MicroSIPButton.iss
if errorlevel 1 exit /b 1
echo Build complete: installer\Output\MicroSIPButton-Setup-%VERSION%.exe
