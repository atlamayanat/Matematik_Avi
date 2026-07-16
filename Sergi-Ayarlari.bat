@echo off
REM Matematik Avi - Sergi guc ayarlari (festival oncesi BIR KEZ calistir).
REM SADECE sunlari degistirir (geri almak icin: Sergi-Ayarlari-GeriAl.bat):
REM   - Uyku modu: kapali (fiste takili guc)
REM   - Ekran kapanmasi: kapali
REM   - Hazirda beklet (hibernate) zamanlayicisi: kapali
REM   - Ekran koruyucu: kapali
REM Baska hicbir sisteme/sergi yazilimina DOKUNMAZ. Bildirimler ve Windows
REM Update elle ayarlanmali (bkz. FESTIVAL-REHBERI.md kontrol listesi).

echo Sergi guc ayarlari uygulaniyor...

powercfg /change standby-timeout-ac 0
if errorlevel 1 goto err
powercfg /change monitor-timeout-ac 0
powercfg /change hibernate-timeout-ac 0

reg add "HKCU\Control Panel\Desktop" /v ScreenSaveActive /t REG_SZ /d 0 /f >nul

echo.
echo TAMAM: Uyku ve ekran kapanmasi kapatildi (fiste takiliyken; hemen etkili).
echo Ekran koruyucu ayari yazildi; PC YENIDEN BASLATILINCA kesin etkili olur
echo (kontrol listesindeki son madde zaten yeniden baslatmayi istiyor).
echo Geri almak icin: Sergi-Ayarlari-GeriAl.bat
echo.
echo HATIRLATMA (elle yapilacak):
echo   - Bildirimler: Ayarlar ^> Sistem ^> Bildirimler ^> "Rahatsiz etmeyin"
echo   - Windows Update: 7 gun duraklat
echo.
pause
exit /b 0

:err
echo.
echo [HATA] Guc ayari degistirilemedi (powercfg hatasi, yukariya bakin).
echo.
pause
exit /b 1
