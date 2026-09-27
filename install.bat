@echo off
REM Easy installer for print-cli (Windows).
REM Needs only: Python 3.9+ from https://www.python.org/downloads/
REM Zero pip dependencies — print_cli.py is stdlib-only.
REM Usage: double-click or run `install.bat` in this folder.

where py >nul 2>nul
if %errorlevel%==0 (
  set PY=py
) else (
  set PY=python
)

%PY% --version
if %errorlevel% neq 0 (
  echo ERROR: Python not found. Install from https://www.python.org/downloads/ ^(tick "Add python to PATH"^).
  pause
  exit /b 1
)

%PY% "%~dp0print_cli.py" --help
if %errorlevel% neq 0 exit /b 1

REM Create a print-cli.cmd shim next to this script so `print-cli` works
REM when this folder is on PATH.
(
  echo @echo off
  echo %PY% "%~dp0print_cli.py" %%*
) > "%~dp0print-cli.cmd"

echo.
echo OK: run with: %PY% "%~dp0print_cli.py" list
echo Or add this folder to PATH, then use: print-cli list
echo.
echo Optional ^(better isolation^): pipx install .
echo Optional silent PDFs: %%PY%% -m pip install pywin32
pause
