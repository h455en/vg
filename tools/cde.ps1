# 1. Get current date for the filename
$date = Get-Date -Format "yyyy-MM-dd"
$fileName = "menu_cde_$($date).pdf"

# 2. Configuration
$apiBase = "https://infoconso-cde14.salamandre.tm.fr/API/public/v1/Pdf/218/2/2/"
$params  = "/PDF?AffCon=false&AffEta=false&AffGrpEta=false&AffMen=false"
$url     = "${apiBase}${date}${params}"

# 3. Path Handling (downloads folder in the current directory)
$outputDir = Join-Path -Path $PSScriptRoot -ChildPath "downloads"
if (!(Test-Path $outputDir)) { 
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null 
}
$outputPath = Join-Path -Path $outputDir -ChildPath $fileName

# 4. Execution
Write-Host "--- Starting CDE Download ---" -ForegroundColor Cyan
Write-Host "URL: $url" -ForegroundColor Gray

try {
    Write-Host "Downloading $fileName..." -ForegroundColor Yellow -NoNewline
    Invoke-WebRequest -Uri $url -OutFile $outputPath -ErrorAction Stop
    Write-Host " [SUCCESS]" -ForegroundColor Green
}
catch {
    Write-Host " [FAILED]" -ForegroundColor Red
    Write-Error "Error: $($_.Exception.Message)"
    exit 1 
}