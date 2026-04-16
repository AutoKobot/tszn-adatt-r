@echo off
chcp 65001 >nul
cls

echo ╔══════════════════════════════════════════════╗
echo ║       EduRegistrar — GitHub Feltöltés        ║
echo ╚══════════════════════════════════════════════╝
echo.

:: Módosított fájlok megjelenítése
echo [1/4] Változások áttekintése:
echo ─────────────────────────────────────────────
git status --short
echo.

:: Commit üzenet bekérése
set /p COMMIT_MSG=Commit üzenet (Enter = auto-dátum): 

:: Ha üres, auto-dátum
if "%COMMIT_MSG%"=="" (
    for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set TODAY=%%c-%%b-%%a
    for /f "tokens=1 delims= " %%a in ('time /t') do set HOUR=%%a
    set COMMIT_MSG=Update %TODAY% %HOUR%
)

echo.
echo [2/4] Összes fájl hozzáadása (git add .)...
git add .
if %ERRORLEVEL% neq 0 (
    echo [HIBA] git add sikertelen!
    pause
    exit /b 1
)

echo [3/4] Commit létrehozása...
git commit -m "%COMMIT_MSG%"
if %ERRORLEVEL% neq 0 (
    echo [INFO] Nincs új változás, vagy commit hiba.
    pause
    exit /b 0
)

echo [4/4] Push a GitHub-ra...
git push
if %ERRORLEVEL% neq 0 (
    echo.
    echo [HIBA] Push sikertelen! Ellenőrizd:
    echo   - Internet kapcsolat
    echo   - GitHub hitelesítés (token/kulcs)
    echo   - git remote -v
    pause
    exit /b 1
)

echo.
echo ╔══════════════════════════════════════════════╗
echo ║   ✅  ÉSZ - Sikeresen feltöltve GitHub-ra!  ║
echo ╚══════════════════════════════════════════════╝
echo   Commit: %COMMIT_MSG%
echo.
timeout /t 4 >nul
