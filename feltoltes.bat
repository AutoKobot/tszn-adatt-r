@echo off
cls

echo =======================================================
echo      ISKOLAI ADATBAZIS - AUTOMATIKUS FELTOLTES
echo =======================================================
echo.

echo Jelenlegi valtozasok:
git status -s
echo.

set /p msg="Kerlek add meg a commit uzenetet (vagy nyomj ENTER-t az automatikushoz): "
if "%msg%"=="" set msg="Normativa kalkulator es UX fejlesztesek frissitese"

echo.
echo 1. Fajlok hozzaadasa...
git add .

echo 2. Commit letrehozasa...
git commit -m "%msg%"

echo 3. Feltoltes GitHubra (Push)...
git push

echo.
if %errorlevel% equ 0 (
    echo =======================================================
    echo  [OK] SIKERESEN FELTOLTVE! A Render elinditja a buildet.
    echo =======================================================
) else (
    echo =======================================================
    echo  [HIBA] A feltoltes nem sikerult. Ellenorizd a halozatot!
    echo =======================================================
)
echo.
pause
