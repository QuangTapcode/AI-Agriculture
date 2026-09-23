@echo off
echo Dang kiem tra va khoi phuc public web...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\ensure-public-web.ps1"
if errorlevel 1 (
  echo Khong the khoi phuc public web. Kiem tra Docker va file .local\logs\pages-proxy-update.log
  pause
  exit /b 1
)
start "" "https://agriai-demo.pages.dev"
