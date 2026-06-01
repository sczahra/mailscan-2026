@echo off
setlocal
cd /d "%~dp0"
py -m pip install --user -r requirements.txt
py -m mailscan2026.app_review
pause
