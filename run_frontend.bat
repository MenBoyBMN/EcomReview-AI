@echo off
setlocal
chcp 65001 >nul
title EcomReview AI - Frontend Dev Server (Port 5173)

cd /d "%~dp0frontend"

where npm >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay npm trong PATH. Vui long cai dat Node.js truoc khi chay.
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo [INFO] Chua co thu muc node_modules, dang chay npm install...
    call npm install
    if errorlevel 1 (
        echo [LOI] Cai dat dependencies frontend that bai.
        pause
        exit /b 1
    )
)

echo ==================================================
echo   EcomReview AI - Khoi dong React Vite Frontend
echo   Web URL    : http://localhost:5173
echo   API Proxy  : /api -^> http://127.0.0.1:8000
echo ==================================================
echo.

call npm run dev
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [LOI] Frontend da dung voi ma loi %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%

REM CreBy: MenBoyBMN
