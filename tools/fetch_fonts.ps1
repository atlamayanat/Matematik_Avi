# fetch_fonts.ps1 - Google Fonts'u web/fonts/ altina yerellestirir (cevrimdisi kiosk icin).
# index.html'deki 3 aile (Baloo 2, JetBrains Mono, Space Grotesk) icin css2 CSS'ini modern
# bir UA ile ceker, referans verilen tum .woff2 alt-kumelerini indirir ve url()'leri yerele
# gomulu fonts.css'e yeniden yazar. Tekrar calistirilabilir.
# Kullanim:  powershell -ExecutionPolicy Bypass -File tools\fetch_fonts.ps1
# NOT: ASCII-only tutuldu; PowerShell 5.1 BOM'suz UTF-8'i ANSI okuyup non-ASCII'de patlar.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$web  = Join-Path $root "web"
$fontsDir = Join-Path $web "fonts"
New-Item -ItemType Directory -Force -Path $fontsDir | Out-Null

$cssUrl = "https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700;800&family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@400;500;600;700&display=swap"
$ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

Write-Host "CSS aliniyor..."
$css = (Invoke-WebRequest -Uri $cssUrl -UserAgent $ua -UseBasicParsing).Content

$rx = [regex]"url\((https://[^)]+\.woff2)\)"
$urls = $rx.Matches($css) | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
Write-Host ("{0} woff2 alt-kumesi bulundu, indiriliyor..." -f $urls.Count)

$map = @{}
$i = 0
foreach ($u in $urls) {
  $i++
  $fn = "f$i.woff2"
  Invoke-WebRequest -Uri $u -UserAgent $ua -OutFile (Join-Path $fontsDir $fn) -UseBasicParsing
  $map[$u] = $fn
}

$local = $css
foreach ($u in $map.Keys) { $local = $local.Replace($u, $map[$u]) }
$header = "/* YEREL fontlar - tools/fetch_fonts.ps1 ile uretildi (cevrimdisi kiosk). */`r`n"
Set-Content -Path (Join-Path $fontsDir "fonts.css") -Value ($header + $local) -Encoding UTF8

$total = (Get-ChildItem $fontsDir -Filter *.woff2 | Measure-Object Length -Sum).Sum
Write-Host ("BITTI: {0} woff2 + fonts.css -> {1} (~{2:N0} KB)" -f $map.Count, $fontsDir, ($total/1KB)) -ForegroundColor Green
