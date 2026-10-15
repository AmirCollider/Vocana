@echo off
rem ------------------------------------------------------------------
rem Vocana: find a Python 3.10+ when the folder has no app\runtime.
rem Sets VOCANA_PY to a command (py -3, or python). Exit code 1: none.
rem Only commands, never a path: a path printed by Python and read back
rem by cmd can arrive garbled when it has non-English letters in it.
rem ------------------------------------------------------------------
set "VOCANA_PY="
where py >nul 2>nul
if errorlevel 1 goto :python
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto :python
set "VOCANA_PY=py -3"
exit /b 0
:python
where python >nul 2>nul
if errorlevel 1 exit /b 1
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 exit /b 1
set "VOCANA_PY=python"
exit /b 0
