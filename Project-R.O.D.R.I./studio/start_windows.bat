@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    py -3.12 -m venv .venv
    if errorlevel 1 py -3.11 -m venv .venv
)
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo Open http://127.0.0.1:8000 in your browser.
.venv\Scripts\python.exe run.py
pause
exit /b
:fail
echo Setup failed. Read the error above. Python 3.11 or 3.12 is recommended.
pause
