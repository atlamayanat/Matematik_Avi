@echo off
REM Kiosk'u acilista otomatik baslatmak icin Gorev Zamanlayici gorevi kurar.
REM Cift tikla -> UAC (yonetici) sorar -> gorevi kaydeder.
echo Otomatik baslatma gorevi kuruluyor (yonetici hakki istenecek)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','\"%~dp0Otomatik-Baslatma-Kur.ps1\"'"
