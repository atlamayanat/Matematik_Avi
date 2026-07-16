@echo off
REM Matematik Avi - Sergi guc ayarlarini GERI ALIR (festival sonrasi).
REM Windows'un tipik varsayilanlarina dondurur:
REM   - Ekran kapanmasi: 10 dk, Uyku: 30 dk, Hazirda beklet: 180 dk
REM   - Ekran koruyucu: acik

echo Guc ayarlari varsayilana donduruluyor...

powercfg /change monitor-timeout-ac 10
if errorlevel 1 goto err
powercfg /change standby-timeout-ac 30
powercfg /change hibernate-timeout-ac 180

reg add "HKCU\Control Panel\Desktop" /v ScreenSaveActive /t REG_SZ /d 1 /f >nul

echo.
echo TAMAM: Ekran 10 dk, uyku 30 dk, hazirda beklet 180 dk, ekran koruyucu acik
echo (ekran koruyucu ayari oturum yeniden acilinca kesinlesir).
echo (Bildirimler / Windows Update'i elle actiysan onlari da geri almayi unutma.)
echo.
pause
exit /b 0

:err
echo.
echo [HATA] Guc ayari degistirilemedi (yukariya bakin).
echo.
pause
exit /b 1
