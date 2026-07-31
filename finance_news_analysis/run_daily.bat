@echo off
chcp 65001 >nul
REM ============================================================
REM  股市新闻系统 - 每日自动采集+分析
REM  此文件由 Windows 任务计划程序每天定时调用
REM ============================================================

set PROJECT_DIR=%~dp0
set PYTHON_EXE=C:\Users\Piper\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe

echo ============================================================
echo   股市新闻系统 - 每日自动运行
echo   %date% %time%
echo ============================================================
echo.

cd /d "%PROJECT_DIR%"

REM 运行采集+分析流水线
"%PYTHON_EXE%" run_pipeline.py

echo.
echo 任务执行完毕。
REM 窗口保持5秒后关闭（定时任务运行时无需人工干预）
timeout /t 5 /nobreak >nul