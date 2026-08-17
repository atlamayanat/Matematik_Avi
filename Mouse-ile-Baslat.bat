@echo off
REM Hizli test modu: kamera acmaz. Mouse hareketi=el, basili sol tik=yumruk.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-kiosk.ps1" -MouseInput %*
