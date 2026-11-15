@echo off
setlocal
chcp 65001 >nul
title EcomReview AI - Backend Server (Port 8000)

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Khong tim thay moi truong ao Python tai ".venv\Scripts\python.exe".
    echo Vui long tao .venv va cai dat thu vien truoc khi chay:
    echo     python -m venv .venv
    echo     .venv\Scripts\pip install -r requirements.txt
    echo     .venv\Scripts\pip install -e .
    pause
    exit /b 1
)

if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Chua co file .env, dang sao chep tu .env.example...
        copy /Y ".env.example" ".env" >nul
    )
)

echo ==================================================
echo   EcomReview AI - Khoi dong FastAPI Backend
echo   API URL    : http://localhost:8000
echo   Swagger UI : http://localhost:8000/docs
echo   Health     : http://localhost:8000/api/v1/health
echo ==================================================
echo.

".venv\Scripts\python.exe" -m uvicorn ecomreview.api.main:app --host 0.0.0.0 --port 8000 --reload
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [LOI] Backend da dung voi ma loi %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%

REM CreBy: MenBoyBMN
