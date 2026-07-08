# Otomatik-Baslatma-Kur.ps1 — kiosk'u Windows Gorev Zamanlayici'ya kaydeder.
# Oturum acilista 'start-kiosk.ps1 -Supervise' calisir (bilesenleri canli tutar),
# ve gorev bir sekilde olurse Gorev Zamanlayici onu ~1 dk'da yeniden baslatir.
# Yonetici hakki gerekir (Otomatik-Baslatma-Kur.bat bunu UAC ile saglar).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ps1  = Join-Path $root "start-kiosk.ps1"
$taskName = "MatematikAvi-Kiosk"

if (-not (Test-Path $ps1)) {
  Write-Host "HATA: start-kiosk.ps1 bulunamadi: $ps1" -ForegroundColor Red
  Read-Host "Kapatmak icin Enter"; exit 1
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"{0}`" -Supervise" -f $ps1)

# Oturum acilista (interaktif -> tarayici/GUI icin sart). "Run only when user is logged on".
$trigger = New-ScheduledTaskTrigger -AtLogOn

# Hata olursa yeniden baslat + sinirsiz calisma suresi + pil/idle takilmalari.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
  -Description "Matematik Avi kiosk (start-kiosk.ps1 -Supervise): oturum acilista + hata olursa yeniden baslar." `
  -Force | Out-Null

Write-Host ""
Write-Host "OK: '$taskName' gorevi kuruldu." -ForegroundColor Green
Write-Host "  - Oturum acilista kiosk OTOMATIK baslar (start-kiosk.ps1 -Supervise)."
Write-Host "  - Gorev olurse ~1 dk'da yeniden baslar."
Write-Host "  - Kioski elle durdurmak icin: kokteki Kiosk-Durdur.bat"
Write-Host ""
Write-Host "Kaldirmak icin (yonetici PowerShell):"
Write-Host "  Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
Write-Host ""
Write-Host "NOT: Sergi PC'sinde kiosk hesabina OTOMATIK OTURUM ACMA ayarla ki elektrik"
Write-Host "     kesintisi/gece yeniden baslatmasi sonrasi gorev tetiklenebilsin."
Read-Host "Kapatmak icin Enter"
