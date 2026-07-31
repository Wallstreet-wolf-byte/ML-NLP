@echo off
chcp 65001 >nul
REM ============================================================
REM  股市新闻系统 - 启动网页看板
REM  双击此文件即可在浏览器中查看新闻看板
REM ============================================================

set PROJECT_DIR=%~dp0
set PYTHON_EXE=C:\Users\Piper\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe

cd /d "%PROJECT_DIR%"

echo ============================================================
echo   股市新闻看板启动中...
echo   浏览器访问: http://127.0.0.1:5000
echo   按 Ctrl+C 可停止服务器
echo ============================================================
echo.

REM 启动Flask服务器
"%PYTHON_EXE%" web\app.py

pause