@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL.ps1"
  if errorlevel 1 exit /b 1
)

start "" /B powershell -NoProfile -WindowStyle Hidden -Command "$u='http://127.0.0.1:8765'; for($i=0;$i -lt 60;$i++){try{Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 $u ^| Out-Null; Start-Process $u; exit}catch{Start-Sleep -Seconds 1}}"
echo Retina Pair Lab: http://127.0.0.1:8765
echo 종료하려면 Ctrl+C를 누르세요.
".venv\Scripts\python.exe" -m uvicorn retina.server:app --host 127.0.0.1 --port 8765
endlocal
