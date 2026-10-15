@echo off
rem ------------------------------------------------------------------
rem Vocana Setup - installs Vocana for this Windows user:
rem Start menu, desktop icon, and an entry in Settings - Apps, so Windows
rem can remove it later. No administrator rights are needed.
rem   Setup.bat            opens the installer page of the studio
rem   Setup.bat /silent    installs without asking (for scripts)
rem The folder keeps working without installing - this is optional.
rem ------------------------------------------------------------------
setlocal
cd /d "%~dp0"
if not exist "%~dp0app\launch.py" goto :broken
set "MODE=start --page install"
if /i "%~1"=="/silent" set "MODE=install --silent"
if /i "%~1"=="-silent" set "MODE=install --silent"
if exist "%~dp0app\runtime\python.exe" goto :bundled
call "%~dp0app\setup\find-python.cmd"
if not errorlevel 1 goto :system
call "%~dp0app\setup\no-python.cmd"
if errorlevel 1 goto :fail
if exist "%~dp0app\runtime\python.exe" goto :bundled
goto :fail

:bundled
"%~dp0app\runtime\python.exe" -X utf8 "%~dp0app\launch.py" %MODE%
if errorlevel 1 goto :fail
exit /b 0

:system
%VOCANA_PY% -X utf8 "%~dp0app\launch.py" %MODE%
if errorlevel 1 goto :fail
exit /b 0

:broken
echo.
echo   The "app" folder next to this file is missing. Extract the whole .zip again.
echo.
pause
exit /b 1

:fail
echo.
echo   Setup could not finish. The messages above say why.
echo.
pause
exit /b 1
