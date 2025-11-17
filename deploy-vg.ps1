
# VG deploy

$msg = "AUTO - sky broc 13"
git  commit -am $msg  ; Start-Sleep -Seconds 3; git push


Start-Sleep -Seconds 10

$scrapWf = "SkyScraper v2025.11.16.2" 
$cleanWf = "Clean Old Workflow Runs v0.2"
$brocWf = "Skybroc v0.14"

gh workflow run $scrapWf  --ref main
gh workflow run $brocWf  --ref main

$cutoffDate = "2025-01-15T10:00:00" #example: "2025-11-16T21:30:00"  16/11/2025 at 21:30 (Paris time).
$cutoffDate = "2025-11-17T10:30:00"
$status = 'failure|cancelled' #status → example: completed, success, failure, cancelled, etc.
$status = "completed"
#example: 2025-01-15T10:00:00 example: 2025-01-15T10:00:00 example: 2025-01-15T10:00:00 example: 2025-01-15T10:00:00

gh workflow run $cleanWf -f cutoff_datetime="$cutoffDate" -f status="$status" --ref main


