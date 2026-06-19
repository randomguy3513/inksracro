@echo off
title Ink's Racro - Installer
echo ===========================================
echo    Installing Ink's Racro
echo ===========================================
echo.

where python >nul 2>&1
if %errorlevel%==0 goto haspy

echo Python isn't installed yet. Trying to install it for you...
where winget >nul 2>&1
if %errorlevel%==0 (
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    echo.
    echo Python was installed. Please CLOSE this window, then run
    echo Install AGAIN so it can finish the last step.
    echo.
    pause
    exit /b
)
echo.
echo Couldn't auto-install Python. Please install it from:
echo     https://www.python.org/downloads/
echo IMPORTANT: tick "Add python.exe to PATH" on the first screen.
echo Then run Install again.
echo.
pause
exit /b

:haspy
echo Python found. Setting up the F2 hotkey helper...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install keyboard >nul 2>&1
echo.
echo  All set!  Just double-click  "Start Racro"  to run it.
echo.
pause
