@echo off
rem Vocana: type a line, hear it (renders\say.wav). An empty line quits.
setlocal
cd /d "%~dp0"
if exist "%~dp0app\runtime\python.exe" goto :bundled
call "%~dp0app\setup\find-python.cmd"
if errorlevel 1 goto :nopython
%VOCANA_PY% -X utf8 "%~dp0app\launch.py" say --interactive
goto :end
:bundled
"%~dp0app\runtime\python.exe" -X utf8 "%~dp0app\launch.py" say --interactive
goto :end
:nopython
echo.
echo   Vocana's Python is not in this folder. Open Vocana.bat once first.
echo.
:end
pause
