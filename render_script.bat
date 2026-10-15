@echo off
rem ------------------------------------------------------------------
rem Vocana without the studio: drag one or more script .txt files onto
rem this file. Each becomes renders\<script name>\ (full.wav, one .wav per
rem line, captions, timing.json, credits.txt). VOICEVOX is started for
rem you if it is closed.
rem ------------------------------------------------------------------
setlocal
cd /d "%~dp0"
if "%~1"=="" goto :usage
if exist "%~dp0app\runtime\python.exe" goto :bundled
call "%~dp0app\setup\find-python.cmd"
if errorlevel 1 goto :nopython
:sysloop
if "%~1"=="" goto :done
%VOCANA_PY% -X utf8 "%~dp0app\launch.py" script "%~1"
shift
goto :sysloop

:bundled
if "%~1"=="" goto :done
"%~dp0app\runtime\python.exe" -X utf8 "%~dp0app\launch.py" script "%~1"
shift
goto :bundled

:usage
echo.
echo   Drag a script .txt file and drop it on render_script.bat.
echo   (Or open Vocana.bat for the studio.)
echo.
pause
exit /b 1

:nopython
echo.
echo   Vocana's Python is not in this folder. Open Vocana.bat once first.
echo.
pause
exit /b 1

:done
echo.
pause
exit /b 0
