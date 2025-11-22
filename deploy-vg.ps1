
# VG deploy

$today = Get-Date -Format "dd.MM.yyyy_HH:mm:ss"
$msg = "AUTO - commit SkyScrap - " + $today

$baseUrl = "D:\HASSEN\WORK\PROJ\VG\GH\vg\.github\workflows\"
$scrapYml = Join-Path $baseUrl "skyscrap_run.yml"
$brocYml = Join-Path $baseUrl "skybroc_run.yml"
$cleanYml = Join-Path $baseUrl "cleanup.yaml"

$scrapWf = Get-WorkflowName $scrapYml
$brocWf = Get-WorkflowName $brocYml
$cleanWf = Get-WorkflowName $cleanYml

# === Show the results ===
Write-Host "scrapWf →" $scrapWf -ForegroundColor Green
Write-Host "brocWf  →" $brocWf  -ForegroundColor Cyan
Write-Host "cleanWf →" $cleanWf -ForegroundColor Yellow


$vgUrl = "https://vide-greniers.org/evenements/Paris-75?distance=50&min=2025-11-22&max=2025-11-23&tags%5B0%5D=1"
$brocUrl = "https://brocabrac.fr/ile-de-france/vide-grenier/?d=2025-11-22,2025-11-23"

gh workflow run $scrapWf `
    -f master_url="$vgUrl" `
    --ref main

gh workflow run $brocWf `
    -f master_url="$brocUrl" `
    --ref main


git  commit -am $msg  ; Start-Sleep -Seconds 3; git push

Start-Sleep -Seconds 10

$cutoffDate = "2025-01-15T10:00:00" #example: "2025-11-16T21:30:00"  16/11/2025 at 21:30 (Paris time).
$cutoffDate = "2025-11-17T16:30:00"
$status = 'failure|cancelled' #status → example: completed, success, failure, cancelled, etc.
$status = "completed"
gh workflow run $cleanWf -f cutoff_datetime="$cutoffDate" -f status="$status" --ref main



$vgUrl = "https://vide-greniers.org/evenements/Paris-75?distance=50&min=2025-11-22&max=2025-11-23&tags%5B0%5D=1"
$brocUrl = "https://brocabrac.fr/ile-de-france/vide-grenier/?d=2025-11-22,2025-11-23"

gh workflow run $scrapWf `
    -f master_url="$vgUrl" `
    --ref main




gh workflow run $brocWf `
    -f master_url="$brocUrl" `
    --ref main



# Helper functions_________________________

function Get-WorkflowName {
    param([string]$Path)
    if (-not (Test-Path $Path)) { Write-Warning "Not found: $Path"; return $null }
    
    (Get-Content -Raw $Path) -match '(?m)^\s*name:\s*(.+)' | ForEach-Object {
        return $Matches[1].Trim()
    }
}