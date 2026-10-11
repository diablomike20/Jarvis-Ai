@echo off
setlocal EnableExtensions
title JARVIS AI - Helyi Windows fuggosegek telepitese
cd /d "%~dp0"
echo =========================================================================
echo JARVIS AI - teljes alkalmazas Python-kornyezet telepitese
echo =========================================================================
echo A telepites publikus Python-fuggosegeket es Playwright bongeszot tolthet le.
echo Nem telepit automatikusan XTTS modellt, nem ker hangklonozasi engedelyt,
echo es nem modositja a JARVIS privat hangreferenciajat.
echo Python 3.11 es internetkapcsolat szukseges.
echo.
choice /C IN /M "Inditod a helyi fuggosegek telepiteset? [I]gen / [N]em"
if errorlevel 2 exit /b 1
if exist ".venv\Scripts\python.exe" goto VENV_OK
py -3.11 -m venv .venv
if errorlevel 1 (
 echo Python 3.11 hianyzik, vagy a .venv nem hozhato letre.
 echo Telepitsd a Python 3.11 64-bites valtozatat es a py launchert.
 pause
 exit /b 2
)
:VENV_OK
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto INSTALL_ERROR
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto INSTALL_ERROR
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto INSTALL_ERROR
echo.
echo A telepites kesz. Inditas: START_JARVIS_WINDOWS.bat
echo Magyar hang opcionális: Settings - Audio - Magyar hangmotor elokeszitese.
pause
exit /b 0
:INSTALL_ERROR
echo.
echo A telepites hibaval leallt. A korabban telepitett csomagok megmaradhattak.
echo Vizsgald meg az itt megjeleno pip/Playwright hibauzenetet.
pause
exit /b 1
