# 1. Setup date and filename
$date = Get-Date -Format "yyyy-MM-dd"
$fileName = "menu_cde_$($date).pdf"

# 2. API Configuration
$apiBase = "https://infoconso-cde14.salamandre.tm.fr/API/public/v1/Pdf/218/2/2/"
$params  = "/PDF?AffCon=false&AffEta=false&AffGrpEta=false&AffMen=false"
$url     = "${apiBase}${date}${params}"

Write-Host "--- CDE Download Task ---" -ForegroundColor Cyan
Write-Host "Target: $fileName" -ForegroundColor Gray

# 3. Download directly to the current directory
try {
    Write-Host "Downloading..." -ForegroundColor Yellow -NoNewline
    Invoke-WebRequest -Uri $url -OutFile $fileName -ErrorAction Stop
    Write-Host " [SUCCESS]" -ForegroundColor Green
}
catch {
    Write-Host " [FAILED]" -ForegroundColor Red
    Write-Error "Download failed: $($_.Exception.Message)"
    exit 1
}