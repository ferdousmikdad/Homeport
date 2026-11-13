@echo off
rem Windows: double-click to start Homeport.
rem First run creates .venv and installs requirements; later runs reinstall
rem only when requirements.txt changes. Then starts the server and opens the browser.
setlocal EnableExtensions
title Homeport
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if exist "%VENV_PY%" "%VENV_PY%" -c "import sys" >nul 2>&1 && goto deps

call :find_python
if not defined PY goto nopython
echo Creating .venv ...
if exist .venv rmdir /s /q .venv
%PY% -m venv .venv
if errorlevel 1 goto venvfail

:deps
fc /b requirements.txt .venv\requirements.installed >nul 2>&1
if not errorlevel 1 goto run
echo Installing requirements ...
"%VENV_PY%" -m pip install --upgrade pip >nul
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto pipfail
copy /y requirements.txt .venv\requirements.installed >nul

:run
"%VENV_PY%" launch.py %*
if errorlevel 1 pause
exit /b 0

:find_python
rem Prefer the "py" launcher; plain "python" may be the Microsoft Store stub.
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1 && set "PY=py -3" && goto :eof
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1 && set "PY=python" && goto :eof
goto :eof

:nopython
echo.
echo Python 3.9 or newer is required.
echo Install it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" in the installer, then run this again.
echo.
pause
exit /b 1

:venvfail
echo Could not create the virtual environment (.venv).
pause
exit /b 1

:pipfail
echo Installing the requirements failed - check your internet connection and try again.
pause
exit /b 1
