
# VG deploy

$msg = "AUTO - sky broc 11"
git  commit -am $msg  ; Start-Sleep -Seconds 3; git push


Start-Sleep -Seconds 10

$scrapWf = "SkyScraper v2025.11.15.1" 
gh workflow run $scrapWf  --ref main


$brocWf = "Skybroc v0.13"
gh workflow run $brocWf  --ref main


$cleanWf = "Clean Old Workflow Runs v0.1"
gh workflow run $cleanWf  --ref main

