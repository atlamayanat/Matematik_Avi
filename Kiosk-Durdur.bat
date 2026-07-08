@echo off
REM Gozetimsiz (supervise) kiosk'u temiz durdurur: durdurma bayragi olusturur,
REM start-kiosk.ps1 -Supervise dongusu bunu gorup bilesenleri kapatir.
echo Kiosk durduruluyor...
> "%~dp0KIOSK-DURDUR.flag" echo stop
timeout /t 4 >nul
echo Bitti.
