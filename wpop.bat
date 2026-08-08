@echo off
setlocal
rem wpop launcher: prefer the admin-auto-elevating exe, else run the GUI elevated via the dev venv.
if exist "%~dp0wpop.exe" (
    start "" "%~dp0wpop.exe"
    exit /b 0
)

rem Elevate via PowerShell if not already elevated, then run the GUI.
net session >nul 2>&1
if %errorlevel% equ 0 goto :elevated
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
exit /b

:elevated
set PYWR=%~dp0dev\.venv\Scripts\python.exe
if exist "%PYWR%" (
    "%PYWR%" -m wpop gui
) else (
    python -m wpop gui
)