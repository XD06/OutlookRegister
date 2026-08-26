@echo off
cd /d "%~dp0"
title OutlookRegister-20
echo headless=false max_tasks=20 proxy_file=Webshare
".venv\Scripts\python.exe" -u main.py
pause
