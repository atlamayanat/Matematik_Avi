@echo off
REM Matematik Avi - cift tiklayinca kiosk modunu baslatir.
REM start-kiosk.ps1'i ExecutionPolicy engeline takilmadan calistirir.
REM Parametreler buradan da gecirilebilir, orn:  Matematik-Avi-Baslat.bat -DetectorHost 192.168.1.50
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-kiosk.ps1" %*
