@echo off
setlocal enabledelayedexpansion
title LAG Plant App - Setup

echo.
echo  ================================================================
echo   LAG Plant App - Device Setup
echo  ================================================================
echo.
echo   This will:
echo     1. Install Python if it is not already on this computer
echo     2. Set up the app environment and packages
echo     3. Create a  Desktop shortcut  to open the app
echo     4. Add the app to the  Start Menu
echo.
echo   Requires an internet connection on first install.
echo   Takes about 1-2 minutes.
echo.
echo   Press any key to begin, or close this window to cancel.
echo.
pause > nul

echo.
echo   Running installer...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-LAGPlantApp.ps1"
set INSTALL_RESULT=%errorlevel%

if %INSTALL_RESULT% neq 0 (
    echo.
    echo  ================================================================
    echo   SETUP FAILED  ^(error code %INSTALL_RESULT%^)
    echo.
    echo   Common fixes:
    echo     - Connect to the internet and try again
    echo     - Right-click INSTALL.bat and choose "Run as administrator"
    echo     - Make sure you copied the full LAG Plant App folder
    echo       ^(it must contain app.py^)
    echo  ================================================================
    echo.
    pause
    exit /b %INSTALL_RESULT%
)

echo.
echo  ================================================================
echo   SETUP COMPLETE
echo.
echo   Look for "LAG Plant App" on the Desktop or in the Start Menu.
echo   Double-click it any time to open the app.
echo  ================================================================
echo.
pause
