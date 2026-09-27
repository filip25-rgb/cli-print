@echo off
REM print-cli installer (Windows) — installs everything that's missing.
REM Usage: install.bat [--yes]
REM Needs internet for winget/pip steps. Zero mandatory pip deps.

setlocal
set YES=0
if "%1"=="--yes" set YES=1

where py >nul 2>nul
if %errorlevel%==0 ( set PY=py ) else ( set PY=python )

%PY% --version >nul 2>nul
if %errorlevel% neq 0 (
  echo Python not found.
  where winget >nul 2>nul
  if %errorlevel%==0 (
    if "%YES%"=="1" ( set C= Y ) else ( set /p C="Install Python via winget now? [Y/n] " )
    if /i not "%C%"=="n" (
      winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
      where py >nul 2>nul
      if %errorlevel%==0 ( set PY=py ) else ( set PY=python )
    )
  ) else (
    echo Install Python 3.9+ from https://www.python.org/downloads/ ^(tick "Add python to PATH"^) then re-run.
    pause
    exit /b 1
  )
)
%PY% --version || ( echo ERROR: Python still missing. & pause & exit /b 1 )

%PY% "%~dp0print_cli.py" doctor
if %errorlevel% neq 0 (
  echo --- attempting auto-fix ^(optional pywin32^) ---
  %PY% "%~dp0print_cli.py" doctor --fix
)

REM Shim so `print-cli` works when this folder is on PATH
(
  echo @echo off
  echo %PY% "%~dp0print_cli.py" %%*
) > "%~dp0print-cli.cmd"

echo.
echo Installed: %~dp0print-cli.cmd
echo Easiest:  %PY% "%~dp0print_cli.py"   ^(guided wizard^)
echo Or add this folder to PATH, then:  print-cli list
echo Optional quieter PDFs: %PY% -m pip install pywin32
pause
