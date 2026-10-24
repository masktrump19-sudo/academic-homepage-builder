@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -c "import ahb, fastapi, pypdf, docx, PIL" >nul 2>&1
if not errorlevel 1 goto run
.venv\Scripts\python.exe -m pip install -r requirements.txt -e .
if errorlevel 1 goto fail
:run
.venv\Scripts\python.exe -m ahb serve
goto :eof
:fail
echo Setup failed. Install Python 3.12 or newer, then follow README.md.
pause
