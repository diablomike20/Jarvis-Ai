@echo off
setlocal EnableExtensions
title JARVIS AI - Teljes alkalmazas (magyar hang integracioval)
cd /d "%~dp0"
set "BRAHMA_SKIP_UPDATE=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
if exist ".venv\Scripts\python.exe" (
  set "JARVIS_PY=.venv\Scripts\python.exe"
) else (
  if exist "venv\Scripts\python.exe" (
    set "JARVIS_PY=venv\Scripts\python.exe"
  ) else (
    echo [JARVIS AI] A teljes forraskod megvan, de a Python-kornyezet nincs telepitve.
    echo Futtasd egyszer a TELEPITES_JARVIS_WINDOWS.bat fajlt ezen a gepen.
    echo A magyar XTTS hangot utana kulon engedelyezheted a Settings menuben.
    pause
    exit /b 2
  )
)
echo [JARVIS AI] Az eredeti alkalmazas indul a helyi Python-kornyezettel...
echo [JARVIS AI] GitHub automatikus forraskodfrissites erre az inditasra kikapcsolva.
"%JARVIS_PY%" main.py
set "result=%errorlevel%"
if not "%result%"=="0" (
 echo.
 echo [JARVIS AI] Az inditas hibaval leallt. Nezd meg a hibasort es a FATAL_CRASH.log fajlt.
 pause
)
exit /b %result%
