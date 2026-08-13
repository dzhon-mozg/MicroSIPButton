@echo off
pyinstaller --onefile --windowed --icon=icon.ico --name MicroSIPButton main.py
echo Build complete: dist\MicroSIPButton.exe
