@echo off
REM Gozetimsiz (supervise) kiosk'u temiz durdurur: durdurma bayragi olusturur,
REM start-kiosk.ps1 -Supervise dongusu bunu gorup bilesenleri kapatir.
REM ONEMLI: Bu dosyayi baska klasore KOPYALAMA (bayrak yanlis yere yazilir,
REM kiosk durmaz). Masaustune koymak icin KISAYOL olustur (sag tik > Kisayol).

REM Kopyalanmis mi? Bayragin gozetimcinin izledigi KOK klasore yazilmasi sart;
REM start-kiosk.ps1 yaninda degilsek yanlis yerdeyiz demektir.
if not exist "%~dp0start-kiosk.ps1" (
  echo.
  echo [HATA] Bu dosya proje klasorunun DISINA kopyalanmis gorunuyor.
  echo Bayrak buradan calismaz. Lutfen oyunun kurulu oldugu klasordeki
  echo Kiosk-Durdur.bat'i calistirin ^(veya masaustune KISAYOL olusturun^).
  echo.
  pause
  exit /b 1
)

echo Kiosk durduruluyor...
> "%~dp0KIOSK-DURDUR.flag" echo stop
timeout /t 4 >nul
echo Bitti.
