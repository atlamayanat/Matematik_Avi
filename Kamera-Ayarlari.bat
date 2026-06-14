@echo off
REM Matematik Avi - Kamera ayar penceresi (kamera sec + onizle + kaydet).
cd /d "%~dp0python"
py -3.13 camera_settings.py
if errorlevel 1 python camera_settings.py
