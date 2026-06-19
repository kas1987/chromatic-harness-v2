@echo off
setlocal enabledelayedexpansion

REM LOGHOUSE Server Startup Script (Windows)
REM Starts the LOGHOUSE dashboard server on port 3333

echo.
echo ╔════════════════════════════════════════════════════╗
echo ║          🏛️  LOGHOUSE SERVER STARTUP              ║
echo ╚════════════════════════════════════════════════════╝
echo.

set "LOGHOUSE_DIR=%~dp0LOGHOUSE_SERVER"

REM Check if Node.js is installed
where node >nul 2>nul
if errorlevel 1 (
    echo ❌ Node.js is not installed. Please install Node.js first.
    pause
    exit /b 1
)

echo 📦 Installing dependencies...
cd /d "%LOGHOUSE_DIR%"

REM Install server dependencies
if not exist "node_modules" (
    echo   Setting up server...
    call npm install
    if errorlevel 1 (
        echo ❌ Failed to install server dependencies
        pause
        exit /b 1
    )
)

REM Install client dependencies
if not exist "client\node_modules" (
    echo   Setting up client...
    cd /d "%LOGHOUSE_DIR%\client"
    call npm install
    if errorlevel 1 (
        echo ❌ Failed to install client dependencies
        pause
        exit /b 1
    )
    cd /d "%LOGHOUSE_DIR%"
)

REM Build client if not already built
if not exist "client\build" (
    echo 📦 Building React client...
    cd /d "%LOGHOUSE_DIR%\client"
    call npm run build
    if errorlevel 1 (
        echo ❌ Failed to build client
        pause
        exit /b 1
    )
    cd /d "%LOGHOUSE_DIR%"
)

echo.
echo ✅ Setup complete. Starting LOGHOUSE server...
echo.
echo 🌐 Server will be available at: http://localhost:3333
echo 📡 API endpoint: http://localhost:3333/api
echo.

REM Start the server
set PORT=3333
call node index.js

pause
