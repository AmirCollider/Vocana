@echo off
rem Vocana: there is no app\runtime and no Python 3.10+ on this PC.
rem Offer to download the runtime (about 34 MB, checked by SHA-256).
echo.
echo   Vocana needs its Python runtime, and this copy does not include it.
echo   (The release from amircollider.com/vocana has it built in.)
echo.
echo   It can be downloaded now, once, into this folder: about 34 MB from
echo   python.org and pypi.org, each file checked against its fingerprint.
echo.
choice /c YN /m "  Download it now"
if errorlevel 2 goto :no
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0get-runtime.ps1"
if errorlevel 1 goto :failed
exit /b 0
:no
echo.
echo   Nothing was downloaded. Get the full release from amircollider.com/vocana,
echo   or install Python 3.10+ from python.org and run Vocana.bat again.
exit /b 1
:failed
echo.
echo   The download did not finish. Check the internet connection and try again.
exit /b 1
