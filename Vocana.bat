@echo off
rem ------------------------------------------------------------------
rem Vocana - opens the studio in your browser.
rem Drop a script .txt on this file to open it in the studio.
rem Keep everything in this file plain ASCII: cmd reads .bat files in
rem the console code page, not UTF-8.
rem ------------------------------------------------------------------
setlocal
cd /d "%~dp0"
if exist "%~dp0app\launch.py" goto :found
echo "%~dp0" | find /i "\Temp" >nul
if not errorlevel 1 goto :inzip
goto :broken
:found
if exist "%~dp0app\runtime\python.exe" goto :bundled
call "%~dp0app\setup\find-python.cmd"
if not errorlevel 1 goto :system
call "%~dp0app\setup\no-python.cmd"
if errorlevel 1 goto :fail
if exist "%~dp0app\runtime\python.exe" goto :bundled
goto :fail

:bundled
"%~dp0app\runtime\python.exe" -X utf8 "%~dp0app\launch.py" start %*
if errorlevel 1 goto :fail
exit /b 0

:system
%VOCANA_PY% -X utf8 "%~dp0app\launch.py" start %*
if errorlevel 1 goto :fail
exit /b 0

:inzip
echo.
echo   Vocana is still inside the .zip file.
echo   Right-click the .zip, choose "Extract All...", then open Vocana.bat
echo   from the extracted folder.
echo.
pause
exit /b 1

:broken
echo.
echo   The "app" folder next to this file is missing. Extract the whole .zip again.
echo.
pause
exit /b 1

:fail
echo.
echo   Vocana could not start. The messages above say why.
echo   More help: Guide.html in this folder, section "If something goes wrong".
echo.
pause
exit /b 1
