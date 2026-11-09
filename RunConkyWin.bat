@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Setting up Conky Windows...
  python -m venv .venv
  if errorlevel 1 goto :fail
  ".venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 goto :fail
)

if exist ".venv\Scripts\pythonw.exe" (
  set "PYTHON=%~dp0.venv\Scripts\pythonw.exe"
) else (
  set "PYTHON=%~dp0.venv\Scripts\python.exe"
)
pushd "%~dp0.."
start "" /D "%CD%" "%PYTHON%" -m Conky_Windows --config "%~dp0conkyrc"
popd
exit /b 0

:fail
echo.
echo Conky Windows could not be set up.
pause
exit /b 1
