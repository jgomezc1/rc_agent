@echo off
REM ============================================================================
REM RC Agent — one-click launcher (Windows). No conda required.
REM
REM Starts the FastAPI backend and the Vite frontend in two separate windows
REM using plain Python venvs created by setup.bat.
REM
REM Usage: double-click this file. First time? Run setup.bat first.
REM ============================================================================

setlocal

set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%"

REM --- 1. Read PRODET_ROOT from .env (fallback to default) --------------------
set "PRODET_ROOT=C:\Users\jgomez\Dropbox\ProDes-Core"
if exist "%REPO_ROOT%.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%REPO_ROOT%.env") do (
        if /i "%%a"=="PRODET_ROOT" set "PRODET_ROOT=%%b"
    )
)

REM --- 2. Verify both venvs exist ---------------------------------------------
REM Venvs live in %LOCALAPPDATA%\rc_agent\venvs (outside Dropbox to avoid sync
REM conflicts during pip installs). Created by setup.bat.
set "VENV_HOME=%LOCALAPPDATA%\rc_agent\venvs"
set "BACKEND_PY=%VENV_HOME%\backend\Scripts\python.exe"
set "PRODET_PY=%VENV_HOME%\prodet\Scripts\python.exe"

if not exist "%BACKEND_PY%" (
    echo.
    echo [ERROR] Backend venv not found at:
    echo         %BACKEND_PY%
    echo         Run setup.bat first.
    echo.
    pause
    exit /b 1
)
if not exist "%PRODET_PY%" (
    echo.
    echo [ERROR] ProDet venv not found at:
    echo         %PRODET_PY%
    echo         Run setup.bat first.
    echo.
    pause
    exit /b 1
)
echo [OK] Backend python:  %BACKEND_PY%
echo [OK] ProDet python:   %PRODET_PY%

REM --- 3. Verify backend deps are installed -----------------------------------
"%BACKEND_PY%" -c "import fastapi, uvicorn, langchain, langchain_anthropic, langgraph" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Backend dependencies missing. Re-run setup.bat.
    echo.
    pause
    exit /b 1
)

REM --- 4. Export PRODET_PYTHON so prodet_agent picks it up unambiguously -----
set "PRODET_PYTHON=%PRODET_PY%"

REM --- 5. Launch backend in a new window --------------------------------------
echo [START] Launching FastAPI backend on http://localhost:8000 ...
start "RC Agent — Backend" cmd /k ""%BACKEND_PY%" -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000"

REM --- 6. Launch frontend in a new window -------------------------------------
echo [START] Launching Vite frontend on http://localhost:5273 ...
start "RC Agent — Frontend" cmd /k "cd /d "%REPO_ROOT%frontend" && npm run dev"

echo.
echo Both processes launched in separate windows.
echo Close those windows to stop the servers.
echo.
endlocal
