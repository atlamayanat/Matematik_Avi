# start-kiosk.ps1 — Matematik Avı kiosk başlatıcı (Windows)
# Tek makinede: Python detektörü (--no-preview) + web statik sunucu + tam-ekran tarayıcı.
#
# Kullanım (PowerShell):
#   .\start-kiosk.ps1                       # tek seferlik (tarayıcı kapanınca durur)
#   .\start-kiosk.ps1 -Supervise            # GÖZETİMSİZ KİOSK: bileşenleri canlı tutar,
#                                           #   biri çökerse yeniden başlatır, tümünü loglar
#   .\start-kiosk.ps1 -DetectorHost 192.168.1.50   # detektör başka makinede
#   .\start-kiosk.ps1 -NoDetector           # detektör zaten çalışıyor
#   .\start-kiosk.ps1 -HttpPort 8080 -WsPort 8765
#
# Çıkış:
#   - normal mod: tarayıcıda Alt+F4 (arka süreçler de kapanır).
#   - -Supervise: tarayıcı/dedektör ÇÖKERSE yeniden başlatılır (ESC ile kapanmaz). Durdurmak
#     için kökteki Kiosk-Durdur.bat'a çift tıkla (ya da KIOSK-DURDUR.flag dosyası oluştur).
#
# Loglar: kök\logs\ altına zaman-damgalı (detector_*.err.log, server_*.err.log). Gece oluşan
# arızanın kanıtı burada kalır. Python -u ile satır-tamponsuz yazılır.
#
# Önkoşul: config.json -> "net":{"transport":"ws"|"both"} ve  pip install websockets

param(
  [string]$DetectorHost = "127.0.0.1",   # tarayıcının bağlanacağı detektör IP'si
  [int]$WsPort   = 8765,
  [int]$HttpPort = 8000,
  [switch]$NoDetector,   # detektör başka yerde / zaten açık
  [switch]$NoServer,     # web zaten servis ediliyor
  [switch]$KeepRunning,  # tarayıcı kapanınca arka süreçleri DURDURMA (normal mod)
  [switch]$Supervise,    # bileşenleri canlı tut + çökeni yeniden başlat (gözetimsiz kiosk)
  [switch]$Preview       # detektörü önizleme penceresiyle başlat (varsayılan: --no-preview)
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$web  = Join-Path $root "web"
$py   = Join-Path $root "python"
$cfg  = Join-Path $py "config.json"
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

# --- Python bul ---
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) { Write-Error "Python bulunamadi (python / py PATH'te degil)."; exit 1 }

# --- transport uyarisi ---
if (Test-Path $cfg) {
  try {
    $j = Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
    $t = $null
    if ($j.PSObject.Properties.Name -contains "net") { $t = $j.net.transport }
    if (($null -eq $t) -or ($t -eq "osc")) {
      Write-Warning "config.json net.transport = '$t'. Tarayici veri ALMAZ; 'ws' veya 'both' yapin."
    }
  } catch { Write-Warning "config.json okunamadi/parse edilemedi: $($_.Exception.Message)" }
}

# --- eski log'lari buda (son 40 dosyayi tut, disk sismesin) ---
try {
  Get-ChildItem -Path $logDir -Filter "*.log" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -Skip 40 |
    Remove-Item -Force -ErrorAction SilentlyContinue
} catch {}

function New-LogPath([string]$name, [string]$kind) {
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  return (Join-Path $logDir ("{0}_{1}.{2}.log" -f $name, $stamp, $kind))
}

# --- bileşen başlatıcılar (log yönlendirmeli; -u = satır-tamponsuz, log hemen yazılsın) ---
function Start-Server {
  $serve = Join-Path $py "serve_nocache.py"
  $o = New-LogPath "server" "out"; $e = New-LogPath "server" "err"
  Write-Host "[kiosk] web sunucusu -> http://localhost:$HttpPort  (log: $logDir)"
  return Start-Process -FilePath $python -ArgumentList @("-u", $serve, "$HttpPort", $web) `
    -PassThru -WindowStyle Hidden -RedirectStandardOutput $o -RedirectStandardError $e
}

function Start-Detector {
  $o = New-LogPath "detector" "out"; $e = New-LogPath "detector" "err"
  $argList = @("-u", "main.py")
  if (-not $Preview) { $argList += "--no-preview" }   # kiosk varsayılanı: penceresiz
  Write-Host "[kiosk] dedektor: python $($argList -join ' ')  (log: $logDir)"
  return Start-Process -FilePath $python -ArgumentList $argList -WorkingDirectory $py `
    -PassThru -WindowStyle Minimized -RedirectStandardOutput $o -RedirectStandardError $e
}

function Get-Browser {
  $chrome = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1
  $edge = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($chrome) { return $chrome } elseif ($edge) { return $edge } else { return $null }
}

function Start-Browser {
  $browser = Get-Browser
  if (-not $browser) { Write-Error "Chrome/Edge bulunamadi."; exit 1 }
  # cb=<rastgele>: no-store sunucuyla birlikte ilk açılışta da taze HTML garanti.
  $cb  = Get-Random
  $url = "http://localhost:$HttpPort/?input=ws&host=$DetectorHost&port=$WsPort&cb=$cb"
  # --app + tam ekran: sayfadaki window.close() (ESC) pencereyi gerçekten kapatır.
  # --disable-session-crashed-bubble: çökme sonrası yeniden açılışta "sayfaları geri
  # yükle?" balonu çıkmasın (supervise yeniden-başlatmasında kritik).
  $prof = Join-Path $env:TEMP "matematik-avi-kiosk"
  $bArgs = @(
    "--app=$url",
    "--start-fullscreen",
    "--user-data-dir=$prof",
    "--no-first-run", "--no-default-browser-check", "--disable-fre",
    "--noerrdialogs", "--disable-infobars",
    "--disable-session-crashed-bubble", "--disable-features=Translate",
    "--check-for-update-interval=31536000"
  )
  Write-Host "[kiosk] tarayici: $url"
  return Start-Process -FilePath $browser -ArgumentList $bArgs -PassThru
}

# --- ilk başlatma ---
$srvProc = if (-not $NoServer)   { Start-Server }   else { $null }
$detProc = if (-not $NoDetector) { Start-Detector } else { $null }
Start-Sleep -Seconds 2   # WS (8765) + web (8000) kalksın, sonra tarayıcı bağlansın
$brProc  = Start-Browser

if ($Supervise) {
  # ---- GÖZETİMSİZ KİOSK: bileşenleri canlı tut, çökeni yeniden başlat ----
  $stopFlag = Join-Path $root "KIOSK-DURDUR.flag"
  if (Test-Path $stopFlag) { Remove-Item $stopFlag -Force }
  Write-Host "[kiosk] SUPERVISE aktif — bileşenler canlı tutuluyor. Durdurmak için: Kiosk-Durdur.bat"
  $brCrashT = $null
  while (-not (Test-Path $stopFlag)) {
    if (-not $NoServer -and ($null -eq $srvProc -or $srvProc.HasExited)) {
      Write-Host "[kiosk] $(Get-Date -Format HH:mm:ss)  web sunucusu düştü -> yeniden başlatılıyor"
      $srvProc = Start-Server
    }
    if (-not $NoDetector -and ($null -eq $detProc -or $detProc.HasExited)) {
      Write-Host "[kiosk] $(Get-Date -Format HH:mm:ss)  dedektör düştü -> yeniden başlatılıyor"
      $detProc = Start-Detector
    }
    if ($null -eq $brProc -or $brProc.HasExited) {
      # crash-loop koruması: tarayıcı 8 sn'den kısa sürede tekrar tekrar ölüyorsa bekle
      $nowT = Get-Date
      if ($brCrashT -and ($nowT - $brCrashT).TotalSeconds -lt 8) { Start-Sleep -Seconds 5 }
      $brCrashT = $nowT
      Write-Host "[kiosk] $(Get-Date -Format HH:mm:ss)  tarayıcı düştü -> yeniden açılıyor"
      Start-Sleep -Milliseconds 500
      $brProc = Start-Browser
    }
    Start-Sleep -Seconds 3
  }
  Write-Host "[kiosk] durdurma bayrağı bulundu -> kapatılıyor."
  Remove-Item $stopFlag -Force -ErrorAction SilentlyContinue
  foreach ($p in @($brProc, $detProc, $srvProc)) {
    if ($p -and -not $p.HasExited) { try { $p.Kill() } catch {} }
  }
}
elseif (-not $KeepRunning) {
  # ---- normal mod: tarayıcı kapanınca arka süreçleri durdur ----
  $brProc.WaitForExit()
  Write-Host "[kiosk] tarayıcı kapandı -> arka süreçler durduruluyor."
  foreach ($p in @($detProc, $srvProc)) {
    if ($p -and -not $p.HasExited) { try { $p.Kill() } catch {} }
  }
}
