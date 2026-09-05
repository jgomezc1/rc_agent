@echo off
REM ============================================================================
REM RC Agent — one-time setup (Windows). No conda required.
REM
REM Creates two Python virtual environments under %LOCALAPPDATA%\rc_agent\venvs
REM (outside Dropbox, so pip installs are not broken by sync file locks):
REM   1. ...\venvs\prodet    - ProDet's deps (Python 3.9 strict)
REM   2. ...\venvs\backend   - rc_agent backend's deps (langchain, fastapi)
REM
REM Run this once before `start.bat`. Safe to re-run; it skips work that's done.
REM ============================================================================

setlocal EnableDelayedExpansion

set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%"

REM --- 1. Read PRODET_ROOT from .env (fallback to default) --------------------
set "PRODET_ROOT=C:\Users\jgomez\Dropbox\ProDes-Core"
if exist "%REPO_ROOT%.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%REPO_ROOT%.env") do (
        if /i "%%a"=="PRODET_ROOT" set "PRODET_ROOT=%%b"
    )
)
echo [INFO] PRODET_ROOT = %PRODET_ROOT%

if not exist "%PRODET_ROOT%\core\main.py" (
    echo.
    echo [ERROR] PRODET_ROOT does not look right: "%PRODET_ROOT%"
    echo         Expected to find core\main.py inside.
    echo         Edit .env and set PRODET_ROOT to your ProDes-Core checkout.
    echo.
    pause
    exit /b 1
)

REM --- 2. Locate Python 3.9 for the ProDet venv -------------------------------
REM ProDet's requirements.txt is pinned and explicitly requires Python 3.9.
set "PY39="
where py >nul 2>&1
if %ERRORLEVEL%==0 (
    py -3.9 -c "import sys; sys.exit(0)" >nul 2>&1
    if !ERRORLEVEL!==0 set "PY39=py -3.9"
)
if not defined PY39 (
    where python3.9 >nul 2>&1
    if !ERRORLEVEL!==0 set "PY39=python3.9"
)
if not defined PY39 (
    echo.
    echo [ERROR] Python 3.9 is required for ProDet but was not found.
    echo         Install it from https://www.python.org/downloads/release/python-3913/
    echo         and re-run setup.bat. The "py" launcher should pick it up.
    echo.
    pause
    exit /b 1
)
echo [OK] ProDet Python 3.9: %PY39%

REM --- 3. Locate a Python (>=3.10) for the backend venv -----------------------
REM langchain / langgraph / fastapi prefer newer Python. Try 3.12, 3.11, 3.10.
set "PY_BACKEND="
for %%v in (3.12 3.11 3.10) do (
    if not defined PY_BACKEND (
        py -%%v -c "import sys; sys.exit(0)" >nul 2>&1
        if !ERRORLEVEL!==0 set "PY_BACKEND=py -%%v"
    )
)
if not defined PY_BACKEND (
    REM Fall back to the same 3.9 used for ProDet — it still works.
    set "PY_BACKEND=%PY39%"
    echo [WARN] No Python 3.10+ found; using 3.9 for the backend too.
) else (
    echo [OK] Backend Python: %PY_BACKEND%
)

REM --- IMPORTANT: venvs MUST live outside Dropbox/OneDrive ---------------------
REM Dropbox locks files while syncing, which breaks pip mid-install. We place
REM venvs in %LOCALAPPDATA% (C:\Users\<you>\AppData\Local) — local SSD, never
REM synced. Only your projects stay in Dropbox; the heavy venv folders don't.
set "VENV_HOME=%LOCALAPPDATA%\rc_agent\venvs"
if not exist "%VENV_HOME%" mkdir "%VENV_HOME%"

REM --- 4. Clean up any old venv inside Dropbox (left over from earlier attempts)
if exist "%PRODET_ROOT%\.venv" (
    echo [CLEANUP] Removing old venv inside Dropbox: %PRODET_ROOT%\.venv
    rmdir /s /q "%PRODET_ROOT%\.venv" 2>nul
)
if exist "%REPO_ROOT%.venv" (
    echo [CLEANUP] Removing old venv inside Dropbox: %REPO_ROOT%.venv
    rmdir /s /q "%REPO_ROOT%.venv" 2>nul
)

REM --- 5. Create ProDet venv if missing ---------------------------------------
set "PRODET_VENV=%VENV_HOME%\prodet"
if exist "%PRODET_VENV%\Scripts\python.exe" (
    echo [SKIP] ProDet venv already exists at %PRODET_VENV%
) else (
    echo [CREATE] ProDet venv at %PRODET_VENV% ...
    %PY39% -m venv "%PRODET_VENV%"
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Failed to create ProDet venv.
        pause
        exit /b 1
    )
)

REM --- 6. Install ProDet's requirements ---------------------------------------
echo [INSTALL] ProDet requirements ...
"%PRODET_VENV%\Scripts\python.exe" -m pip install --upgrade pip
"%PRODET_VENV%\Scripts\python.exe" -m pip install -r "%PRODET_ROOT%\requirements.txt"
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Failed to install ProDet requirements.
    pause
    exit /b 1
)

REM --- 7. Create backend venv if missing --------------------------------------
set "BACKEND_VENV=%VENV_HOME%\backend"
if exist "%BACKEND_VENV%\Scripts\python.exe" (
    echo [SKIP] Backend venv already exists at %BACKEND_VENV%
) else (
    echo [CREATE] Backend venv at %BACKEND_VENV% ...
    %PY_BACKEND% -m venv "%BACKEND_VENV%"
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Failed to create backend venv.
        pause
        exit /b 1
    )
)

REM --- 8. Install backend requirements ----------------------------------------
echo [INSTALL] Backend requirements ...
"%BACKEND_VENV%\Scripts\python.exe" -m pip install --upgrade pip
"%BACKEND_VENV%\Scripts\python.exe" -m pip install -r "%REPO_ROOT%requirements.txt"
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Failed to install backend requirements.
    pause
    exit /b 1
)

REM --- 9. Install frontend deps if node_modules is missing --------------------
if not exist "%REPO_ROOT%frontend\node_modules" (
    echo [INSTALL] Frontend npm packages ...
    pushd "%REPO_ROOT%frontend"
    call npm install
    popd
) else (
    echo [SKIP] frontend\node_modules already exists.
)

echo.
echo ============================================================================
echo [DONE] Setup complete.
echo.
echo   ProDet python:   %PRODET_VENV%\Scripts\python.exe
echo   Backend python:  %BACKEND_VENV%\Scripts\python.exe
echo.
echo   Next: double-click start.bat to launch the app.
echo ============================================================================
echo.
pause
endlocal
