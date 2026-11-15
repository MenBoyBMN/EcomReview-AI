@echo off
setlocal
chcp 65001 >nul
title EcomReview AI - Standalone Frontend (Port 5173)

cd /d "%~dp0"

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

echo ==============================================================
echo   EcomReview AI - Khoi dong Standalone Frontend
echo   Web URL : http://localhost:5173/overview
echo   Che do  : Tu dong (Ket noi Backend 8000 hoac Chay Doc Lap)
echo ==============================================================
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
