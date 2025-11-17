
# VG deploy



$DateStr = $Date.ToString("yyyy.MM.dd_HH:ss")


$msg = "AUTO - commit SkyScrap - " + $DateStr

$scrapYml = "D:\HASSEN\WORK\PROJ\VG\GH\vg\.github\workflows\skyscrap_run.yml"
$brocYml = "D:\HASSEN\WORK\PROJ\VG\GH\vg\.github\workflows\skyscrap_run.yml"
$cleanYml = "D:\HASSEN\WORK\PROJ\VG\GH\vg\.github\workflows\skyscrap_run.yml"


$scrapWf = gc $scrapYml | Select-String "name:" | Select-Object -First 1
$brocWf = gc $brocYml | Select-String "name:" | Select-Object -First 1
$cleanWf = gc $cleanYml | Select-String "name:" | Select-Object -First 1


#$scrapWf = "SkyScraper v2025.11.16.3" 
#$cleanWf = "Clean Old Workflow Runs v0.2"
#$brocWf = "Skybroc v0.15"


git  commit -am $msg  ; Start-Sleep -Seconds 3; git push


Start-Sleep -Seconds 10



gh workflow run $scrapWf  --ref main
gh workflow run $brocWf  --ref main

$cutoffDate = "2025-01-15T10:00:00" #example: "2025-11-16T21:30:00"  16/11/2025 at 21:30 (Paris time).
$cutoffDate = "2025-11-17T16:30:00"
$status = 'failure|cancelled' #status → example: completed, success, failure, cancelled, etc.
$status = "completed"
gh workflow run $cleanWf -f cutoff_datetime="$cutoffDate" -f status="$status" --ref main



$vgUrl = "https://vide-greniers.org/evenements/Paris-75?distance=50&min=2025-11-22&max=2025-11-23&tags%5B0%5D=1"

gh workflow run $scrapWf `
    -f master_url="$vgUrl" `
    --ref main


$brocUrl = "https://brocabrac.fr/ile-de-france/vide-grenier/?d=2025-11-22,2025-11-23"

gh workflow run $brocWf `
    -f master_url="$brocUrl" `
    --ref main