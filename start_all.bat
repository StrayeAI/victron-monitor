@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Victron Monitor REV18

echo ==========================================
echo  Victron Monitor REV18
echo ==========================================
echo.

echo REV18 bruker IKKE pip og IKKE .venv.
echo Den starter direkte med ferdig datafil.
echo.

for %%F in (app.py data\products.json) do (
  if not exist "%%F" (
    echo FEIL: Mangler %%F i denne mappen.
    echo Hoyreklikk REV18-mappen i OneDrive og velg "Behold alltid pa denne enheten", og prov igjen.
    pause
    exit /b 1
  )
  echo Sjekker/laster ned %%F ...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -LiteralPath '%%F' -Raw | Out-Null"
  if errorlevel 1 (
    echo FEIL: Klarte ikke lese %%F.
    pause
    exit /b 1
  )
)

set "PY="
where py >nul 2>nul && set "PY=py -3"
if "%PY%"=="" where python >nul 2>nul && set "PY=python"
if "%PY%"=="" (
  echo FEIL: Python ble ikke funnet.
  echo Installer Python 3 fra Microsoft Store eller python.org.
  pause
  exit /b 1
)

echo Starter Victron Monitor REV18...
start "" http://127.0.0.1:8765
%PY% app.py
pause
