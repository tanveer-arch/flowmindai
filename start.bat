@echo off
echo ================================================
echo  FlowMind AI — NexaMind 2026
echo  Starting unified backend (port 8081)
echo ================================================
echo.

cd /d "%~dp0"

REM Install dependencies if needed
echo [1/3] Checking Python dependencies...
pip install -r requirements.txt -q

REM Start backend
echo [2/3] Starting backend on http://localhost:8081 ...
start "FlowMind Backend" cmd /k "python -m uvicorn backend.app:app --host 0.0.0.0 --port 8081 --reload"

REM Wait for backend to boot
timeout /t 3 /nobreak >nul

REM Start frontend
echo [3/3] Starting frontend on http://localhost:3000 ...
start "FlowMind Frontend" cmd /k "python -m http.server 3000 --directory frontend"

REM Wait a bit then open browser
timeout /t 2 /nobreak >nul
start "" "http://localhost:3000/login.html"

echo.
echo ================================================
echo  FlowMind is running!
echo  Backend:  http://localhost:8081
echo  Frontend: http://localhost:3000
echo  API docs: http://localhost:8081/docs
echo ================================================
echo.
pause
