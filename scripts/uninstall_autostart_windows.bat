@echo off
rem Stop Homeport from starting when you sign in to Windows.
set "FILE=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Homeport.cmd"
if exist "%FILE%" (
  del "%FILE%"
  echo Removed the Homeport startup entry.
) else (
  echo Homeport is not set to start at sign-in.
)
pause
