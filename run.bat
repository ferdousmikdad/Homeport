@echo off
rem Windows: double-click to start Homeport - nothing needs to be installed first.
rem   1. Already set up?               -> start right away.
rem   2. Python 3.9+ on this computer? -> use it to set up .venv.
rem   3. No Python?                    -> download a private copy (via uv) into
rem                                       .runtime\ in this folder. No admin needed.
rem Requirements are (re)installed only when requirements.txt changes.
setlocal EnableExtensions
title Homeport
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"
set "RUNTIME=%CD%\.runtime"
set "UV=%RUNTIME%\uv.exe"
rem Keep everything uv downloads inside this folder.
set "UV_PYTHON_INSTALL_DIR=%RUNTIME%\python"
set "UV_CACHE_DIR=%RUNTIME%\cache"

if exist "%VENV_PY%" "%VENV_PY%" -c "import sys" >nul 2>&1 && goto deps
if exist .venv rmdir /s /q .venv

if defined HOMEPORT_FORCE_DOWNLOAD goto uvsetup
call :find_python
if not defined PY goto uvsetup
echo Setting up with Python from this computer ...
%PY% -m venv .venv
if errorlevel 1 goto uvsetup
goto deps

:uvsetup
call :get_uv
if errorlevel 1 goto dlfail
set "UV_PYTHON_PREFERENCE=only-managed"
"%UV%" venv --quiet --python 3.12 .venv
if errorlevel 1 goto venvfail

:deps
fc /b requirements.txt .venv\requirements.installed >nul 2>&1
if not errorlevel 1 goto run
echo Installing requirements ...
"%VENV_PY%" -m pip --version >nul 2>&1
if errorlevel 1 goto uvinstall
"%VENV_PY%" -m pip install --quiet --upgrade pip
"%VENV_PY%" -m pip install --quiet -r requirements.txt
if errorlevel 1 goto pipfail
goto stamp

:uvinstall
rem a .venv made by uv has no pip
call :get_uv
if errorlevel 1 goto dlfail
"%UV%" pip install --quiet --python "%VENV_PY%" -r requirements.txt
if errorlevel 1 goto pipfail
if exist "%RUNTIME%\cache" rmdir /s /q "%RUNTIME%\cache"

:stamp
copy /y requirements.txt .venv\requirements.installed >nul

:run
"%VENV_PY%" launch.py %*
if errorlevel 1 pause
exit /b 0

:find_python
rem Prefer the "py" launcher; plain "python" may be the Microsoft Store stub.
set "PY="
py -3 -c "import sys, venv, ensurepip; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1 && set "PY=py -3" && goto :eof
python -c "import sys, venv, ensurepip; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1 && set "PY=python" && goto :eof
goto :eof

:get_uv
if exist "%UV%" exit /b 0
where curl.exe >nul 2>&1 || exit /b 1
where tar.exe >nul 2>&1 || exit /b 1
echo Python wasn't found - downloading a private copy into .runtime (one time, about 40 MB) ...
if not exist "%RUNTIME%" mkdir "%RUNTIME%"
set "UVZIP=uv-x86_64-pc-windows-msvc.zip"
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "UVZIP=uv-aarch64-pc-windows-msvc.zip"
curl.exe -fsSL -o "%RUNTIME%\uv.zip" "https://github.com/astral-sh/uv/releases/latest/download/%UVZIP%"
if errorlevel 1 exit /b 1
tar.exe -xf "%RUNTIME%\uv.zip" -C "%RUNTIME%"
if errorlevel 1 exit /b 1
del "%RUNTIME%\uv.zip"
if not exist "%UV%" exit /b 1
exit /b 0

:dlfail
echo.
echo Couldn't download Python automatically (no internet, or Windows older than 10).
echo Install Python 3.9+ from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" in the installer, then run this again.
echo.
pause
exit /b 1

:venvfail
echo Could not create the Python environment (.venv).
pause
exit /b 1

:pipfail
echo Installing the requirements failed - check your internet connection and try again.
pause
exit /b 1
