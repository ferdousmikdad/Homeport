@echo off
rem Start Homeport in the background every time you sign in to Windows.
rem Adds a small launcher to your Startup folder (no admin rights needed).
setlocal
cd /d "%~dp0.."
set "DIR=%CD%"
if not exist "%DIR%\.venv\Scripts\pythonw.exe" (
  echo Run run.bat once first so the .venv folder is created.
  pause
  exit /b 1
)
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
(
  echo @echo off
  echo cd /d "%DIR%"
  echo start "" "%DIR%\.venv\Scripts\pythonw.exe" "%DIR%\launch.py" --no-browser
) > "%STARTUP%\Homeport.cmd"
echo Installed: "%STARTUP%\Homeport.cmd"
echo Homeport will start in the background when you sign in.
pause
