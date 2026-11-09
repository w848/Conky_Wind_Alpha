@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "PROJECT_NAME=%%~nxI"
if not defined PROJECT_NAME set "PROJECT_NAME=Conky_Windows"

cd /d "%SCRIPT_DIR%"

if not exist ".venv\Scripts\python.exe" (
  echo Setting up Conky Windows...
  python -m venv .venv
  if errorlevel 1 goto :fail
  ".venv\Scripts\python.exe" -m pip install -r "%SCRIPT_DIR%requirements.txt"
  if errorlevel 1 goto :fail
)

if exist ".venv\Scripts\pythonw.exe" (
  set "PYTHON=%SCRIPT_DIR%.venv\Scripts\pythonw.exe"
) else (
  set "PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe"
)
pushd "%SCRIPT_DIR%.."
start "" /D "%CD%" "%PYTHON%" -m %PROJECT_NAME% --config "%SCRIPT_DIR%conkyrc"
popd
exit /b 0

:fail
echo.
echo Conky Windows could not be set up.
pause
exit /b 1
