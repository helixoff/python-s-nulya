@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 app.py
) else (
    python app.py
)
if errorlevel 1 (
    echo.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/
    echo Enable "Add python.exe to PATH" and install Tcl/Tk.
    echo Open START-HERE.html for instructions.
    pause
)
