@echo off
setlocal
cd /d "%~dp0"
git add .
git commit -m "Seed MailScan 2026 full GUI skeleton"
git push origin main
pause
