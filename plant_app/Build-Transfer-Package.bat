@echo off
setlocal enabledelayedexpansion
title LAG Plant App - Build Transfer Package

echo.
echo  ================================================================
echo   LAG Plant App - Build Transfer Package
echo  ================================================================
echo.
echo   This creates a ZIP file you can copy to any other Windows PC.
echo   The ZIP includes all app files and offline Python packages so
echo   the other device does NOT need an internet connection.
echo.
echo   Output: dist\LAG-Plant-App-Installer.zip
echo.
echo   Takes a few minutes to download the offline packages.
echo.
echo   Press any key to begin, or close this window to cancel.
echo.
pause > nul

echo.
echo   Building package (downloading offline packages)...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_install_package.ps1" -DownloadWheels -Zip
set BUILD_RESULT=%errorlevel%

if %BUILD_RESULT% neq 0 (
    echo.
    echo  ================================================================
    echo   BUILD FAILED  ^(error code %BUILD_RESULT%^)
    echo.
    echo   Make sure you are connected to the internet and try again.
    echo  ================================================================
    echo.
    pause
    exit /b %BUILD_RESULT%
)

echo.
echo  ================================================================
echo   PACKAGE READY
echo.
echo   File: dist\LAG-Plant-App-Installer.zip
echo.
echo   To install on another device:
echo     1. Copy that ZIP to the other PC
echo     2. Extract the ZIP to any folder
echo     3. Double-click  INSTALL.bat  inside the extracted folder
echo  ================================================================
echo.
pause
