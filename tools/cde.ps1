# 1. Date Logic (French)
$culture = [System.Globalization.CultureInfo]::GetCultureInfo("fr-FR")
$rawDate = Get-Date
$dateString = $rawDate.ToString("dd_MMM_yyyy", $culture).Replace(".", "").ToLower()
$fileName = "menu_cde_$($dateString).pdf"

# 2. Paths
$templatePath = "docs/template.html"
$outputPath   = "docs/cde.html"
$pdfPath      = "docs/$fileName"

# 3. Download PDF
$apiDate = $rawDate.ToString("yyyy-MM-dd")
$url = "https://infoconso-cde14.salamandre.tm.fr/API/public/v1/Pdf/218/2/2/$($apiDate)/PDF?AffCon=false&AffEta=false&AffGrpEta=false&AffMen=false"

try {
    Write-Host "Downloading PDF..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $url -OutFile $pdfPath -ErrorAction Stop

    # 4. Update HTML from Template
    if (Test-Path $templatePath) {
        $html = Get-Content $templatePath -Raw
        $html = $html.Replace("{{FULL_DATE}}", $rawDate.ToString("dd MMMM yyyy", $culture))
        $html = $html.Replace("{{FILENAME}}", $fileName)
        $html = $html.Replace("{{TIME}}", $rawDate.ToString("HH:mm"))
        
        $html | Out-File -FilePath $outputPath -Encoding utf8
        Write-Host "Updated cde.html successfully." -ForegroundColor Green
    }

    # Export for GitHub
    if ($env:GITHUB_ENV) {
        "ARTIFACT_NAME=$($fileName.Replace('.pdf', ''))" | Out-File -FilePath $env:GITHUB_ENV -Append
        "FILE_NAME=$fileName" | Out-File -FilePath $env:GITHUB_ENV -Append
    }
}
catch {
    Write-Error "Process failed: $($_.Exception.Message)"
    exit 1
}