@echo off
rem ==========================================================================
rem  Sahte Site Avcilari - starts the backend (FastAPI) and frontend (Vite).
rem
rem  Double-click this file. Each application opens in its own window.
rem  Stop an application with Ctrl+C in its window, then close the window.
rem
rem  Commands and ports are the documented ones:
rem    backend : python -m uvicorn app.main:app --reload --port 8000  (in backend\)
rem    frontend: npm run dev  -> vite, port 5173 from vite.config.ts   (in frontend\)
rem  This script installs nothing and never changes code or the database.
rem ==========================================================================
setlocal EnableExtensions DisableDelayedExpansion
title Sahte Site Avcilari - Launcher

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"
set "FAILED="

echo.
echo  Sahte Site Avcilari - launcher
echo  Project folder: "%ROOT%"
echo.
echo  Checking requirements...

rem ---- Project files -------------------------------------------------------
rem Descriptions must not contain parentheses: they would close the if-block in :need_file.
call :need_file "%BACKEND%\app\main.py" "Backend entry point: backend\app\main.py"
call :need_file "%FRONTEND%\package.json" "Frontend package file: frontend\package.json"

if not exist "%BACKEND%\.env" (
    echo  [MISSING] backend\.env
    echo            Copy backend\.env.example to backend\.env and enter your MySQL settings.
    set "FAILED=1"
) else (
    findstr /C:"__ENTER_YOUR_PASSWORD__" "%BACKEND%\.env" >nul 2>&1 && (
        echo  [MISSING] DB_PASSWORD in backend\.env still contains the placeholder value.
        set "FAILED=1"
    )
)

if not exist "%FRONTEND%\node_modules\.bin\vite.cmd" (
    echo  [MISSING] Frontend dependencies ^(frontend\node_modules^).
    echo            Run once:  cd frontend  then  npm install
    set "FAILED=1"
)

rem ---- Tools ---------------------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo  [MISSING] Python was not found on PATH.
    set "FAILED=1"
    goto :check_node
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo  [MISSING] A working Python 3.10 or newer is required.
    echo            ^(The Microsoft Store "python" shortcut does not count.^)
    set "FAILED=1"
    goto :check_node
)
python -c "import fastapi, uvicorn, sqlalchemy, pymysql, alembic, pydantic_settings, rapidfuzz, tldextract, idna, confusable_homoglyphs, playwright" >nul 2>&1
if errorlevel 1 (
    echo  [MISSING] Backend Python packages.
    echo            Run once:  python -m pip install -r backend\requirements.txt
    set "FAILED=1"
)

:check_node
where node >nul 2>&1
if errorlevel 1 (
    echo  [MISSING] Node.js was not found on PATH.
    set "FAILED=1"
)
rem npm is a .cmd script: "call" is required, otherwise this script would stop after it.
where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo  [MISSING] npm was not found on PATH.
    set "FAILED=1"
) else (
    call npm --version >nul 2>&1
    if errorlevel 1 (
        echo  [MISSING] npm is installed but does not run correctly.
        set "FAILED=1"
    )
)

if defined FAILED goto :fail

rem ---- Ports ---------------------------------------------------------------
call :check_port %BACKEND_PORT% "Backend"
call :check_port %FRONTEND_PORT% "Frontend"
if defined FAILED goto :fail

echo  All checks passed.
echo.

rem ---- Launch --------------------------------------------------------------
rem "cmd /k" keeps each window open, so logs and startup errors stay visible.
rem The backend checks the database and creates missing tables on startup.
start "Sahte Site Avcilari - Backend (port %BACKEND_PORT%)" /D "%BACKEND%" cmd /k python -m uvicorn app.main:app --reload --port %BACKEND_PORT%
start "Sahte Site Avcilari - Frontend (port %FRONTEND_PORT%)" /D "%FRONTEND%" cmd /k npm run dev

echo  Started in separate windows:
echo    Backend   http://localhost:%BACKEND_PORT%    (API docs: http://localhost:%BACKEND_PORT%/docs)
echo    Frontend  http://localhost:%FRONTEND_PORT%
echo.
echo  Waiting for both applications to listen (up to 60 seconds)...
call :wait_port %BACKEND_PORT% "Backend"
call :wait_port %FRONTEND_PORT% "Frontend"
echo.
echo  Open http://localhost:%FRONTEND_PORT% in your browser.
echo  To stop: press Ctrl+C in the Backend and Frontend windows, then close them.
echo.
echo  This launcher window can be closed; the applications keep running.
pause
exit /b 0

rem ==========================================================================
:fail
echo.
echo  Nothing was started. Fix the items above and run baslat.bat again.
echo.
pause
exit /b 1

rem --------------------------------------------------------------------------
:need_file
if not exist "%~1" (
    echo  [MISSING] %~2
    set "FAILED=1"
)
exit /b 0

rem --------------------------------------------------------------------------
rem Reports (but never stops) a process that already listens on the port.
:check_port
set "PORT_OWNER="
for /f "usebackq delims=" %%L in (`powershell -NoProfile -Command "$c = Get-NetTCPConnection -State Listen -LocalPort %~1 -ErrorAction SilentlyContinue | Select-Object -First 1; if ($c) { $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue; Write-Output ($p.ProcessName + ', PID ' + $c.OwningProcess) }"`) do set "PORT_OWNER=%%L"
if defined PORT_OWNER (
    echo  [PORT IN USE] %~2 port %~1 is already used by %PORT_OWNER%.
    echo                The application may already be running. Stop that process yourself, or use the running one.
    set "FAILED=1"
)
exit /b 0

rem --------------------------------------------------------------------------
:wait_port
powershell -NoProfile -Command "$end = (Get-Date).AddSeconds(60); while ((Get-Date) -lt $end) { if (Get-NetTCPConnection -State Listen -LocalPort %~1 -ErrorAction SilentlyContinue) { exit 0 }; Start-Sleep -Milliseconds 500 }; exit 1" >nul 2>&1
if errorlevel 1 (
    echo    %~2: not listening yet on port %~1 - check the %~2 window for errors.
) else (
    echo    %~2: running on port %~1.
)
exit /b 0
