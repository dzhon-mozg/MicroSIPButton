@echo off
set MSIP=%LOCALAPPDATA%\MicroSIP\microsip.exe
set MBTN=%~dp0dist\MicroSIPButton.exe
if not exist "%MSIP%" echo MicroSIP not found: %MSIP% && pause && exit /b 1
if not exist "%MBTN%" echo MicroSIPButton.exe not found: %MBTN% && pause && exit /b 1
start "" "%MSIP%"
start "" "%MBTN%"
