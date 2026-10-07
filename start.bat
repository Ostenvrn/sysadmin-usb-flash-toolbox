@echo off
REM =====================================================================
REM Запуск sysadmin-usb на Windows.
REM Использует портативный Python из папки python\.
REM =====================================================================

REM Проверяем, есть ли портативный Python
if exist "python\python.exe" (
    echo [INFO] Используем портативный Python
    python\python.exe app\main.py
) else (
    echo [WARN] Портативный Python не найден, используем системный
    python app\main.py
)

REM Пауза, чтобы окно не закрылось
pause
