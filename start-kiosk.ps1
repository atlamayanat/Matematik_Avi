# start-kiosk.ps1 — Matematik Avı kiosk başlatıcı (Windows)
# Tek makinede: Python detektörü (--no-preview) + web statik sunucu + tam-ekran tarayıcı.
#
# Kullanım (PowerShell):
#   .\start-kiosk.ps1
#   .\start-kiosk.ps1 -DetectorHost 192.168.1.50      # detektör başka makinede
#   .\start-kiosk.ps1 -NoDetector                     # detektör zaten çalışıyor
#   .\start-kiosk.ps1 -HttpPort 8080 -WsPort 8765
#
# Çıkış: tarayıcıda Alt+F4 (kiosk). Tarayıcı kapanınca arka süreçler de kapanır.
# Önkoşul: config.json -> "net":{"transport":"ws"|"both"} ve  pip install websockets

param(
  [string]$DetectorHost = "127.0.0.1",   # tarayıcının bağlanacağı detektör IP'si
  [int]$WsPort   = 8765,
  [int]$HttpPort = 8000,
  [switch]$NoDetector,   # detektör başka yerde / zaten açık
  [switch]$NoServer,     # web zaten servis ediliyor
  [switch]$KeepRunning   # tarayıcı kapanınca arka süreçleri DURDURMA
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$web  = Join-Path $root "web"
$py   = Join-Path $root "python"
$cfg  = Join-Path $py "config.json"

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

$bg = @()

# --- 1) web statik sunucu (0.0.0.0:HttpPort) ---
# NOT: serve_nocache.py kullaniyoruz (duz `http.server` degil). Cunku index.html
# surum-busted degil; duz sunucu Cache-Control gondermeyince Chrome eski HTML'i
# onbellekten sunup kalibrasyon giris ekranini atliyordu. no-store -> hep taze.
if (-not $NoServer) {
  Write-Host "[kiosk] web sunucusu (no-store) -> http://localhost:$HttpPort  ($web)"
  $serve = Join-Path $py "serve_nocache.py"
  $bg += Start-Process -FilePath $python `
    -ArgumentList @($serve, "$HttpPort", $web) `
    -PassThru -WindowStyle Hidden
}

# --- 2) detektör (--no-preview) ---
if (-not $NoDetector) {
  Write-Host "[kiosk] detektor baslatiliyor: python main.py --no-preview"
  $bg += Start-Process -FilePath $python `
    -ArgumentList @("main.py","--no-preview") `
    -WorkingDirectory $py -PassThru -WindowStyle Minimized
}

Start-Sleep -Seconds 2

# --- 3) tarayici (Chrome > Edge), kiosk ---
# cb=<rastgele>: var olan eski onbellek girisini atlamak icin (no-store sunucuyla
# birlikte ilk acilis da garanti taze gelir).
$cb  = Get-Random
$url = "http://localhost:$HttpPort/?input=ws&host=$DetectorHost&port=$WsPort&cb=$cb"

$chrome = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

$edge = @(
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

$browser = if ($chrome) { $chrome } elseif ($edge) { $edge } else { $null }
if (-not $browser) { Write-Error "Chrome/Edge bulunamadi."; exit 1 }

# --app + tam ekran: bu modda sayfadaki window.close() (ESC) pencereyi GERCEKTEN
# kapatir ve fazladan karsilama sekmesi acilmaz (--kiosk'ta window.close calismaz).
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

Write-Host "[kiosk] tarayici: $browser"
Write-Host "[kiosk] URL    : $url"
Write-Host "[kiosk] Cikis  : ESC veya Alt+F4 (tarayici + arka surecler kapanir)"
$browserProc = Start-Process -FilePath $browser -ArgumentList $bArgs -PassThru

# --- tarayici kapaninca arka surecleri durdur ---
if (-not $KeepRunning) {
  $browserProc.WaitForExit()
  Write-Host "[kiosk] tarayici kapandi -> arka surecler durduruluyor."
  foreach ($p in $bg) {
    if ($p -and -not $p.HasExited) { try { $p.Kill() } catch {} }
  }
}
