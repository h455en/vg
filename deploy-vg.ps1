
# VG deploy

$msg = "AUTO - sky broc 09"
git  commit -am $msg  ; Start-Sleep -Seconds 3; git push


Start-Sleep -Seconds 10

$wfName = "SkyScraper v2025.11.15.1" 
gh workflow run $wfName  --ref main


# $pmp = "pmp026"
# $version = "0.26"
# Write-Host "Preparing R$version ($pmp)" -ForegroundColor Cyan
# $sources = "D:\HASSEN\WORK\pmpvid\App\"
# $ReleaseFolder = "D:\HASSEN\WORK\pmpvid\Release\"
# $folder = $ReleaseFolder + "App_v" + $version + ".zip"

# $compress = @{
#     LiteralPath      = ($sources + "index.html"), ($sources + "app.js"), ($sources + "style.css")
#     CompressionLevel = "Fastest"
#     DestinationPath  = $folder
# }

# Compress-Archive @compress
# Write-Host "Release $version ($pmp)" -ForegroundColor Green

# Deploy
# Rollback
# Deprecate (all release before version x.yz)
<#
#----------------
# Cleaning
Write-Host "Cleaning ..." -ForegroundColor Cyan
$Src = "D:\HASSEN\WORK\pmpvid\App\"
rm ($Src + "index.html")
rm ($Src + "app.js")
rm ($Src + "style.css")

$v = "0.20"
$version = "_v" + $v + ".zip"
$release = "D:\HASSEN\WORK\pmpvid\Release\"
$zipFolder = $release + "App"+ $version

Write-Host "Rollback to version [$version]" -ForegroundColor Cyan
Expand-Archive -LiteralPath $zipFolder -DestinationPath $Src

Write-Host "Rollback terminated." -ForegroundColor Green
#----------------
#>