$ErrorActionPreference='Stop'
$audit='D:\aaa\maintenance\VIPER_ONLY_THIRDPERSON_CLEANUP_20261127'
& 'D:\aaa\envs\gamecam-vo\python.exe' -u -B (Join-Path $audit 'prepare_retired_entries.py')
if($LASTEXITCODE -ne 0){throw 'Supplementary plan did not pass.'}
$plan=Get-Content -LiteralPath (Join-Path $audit 'SUPPLEMENTARY_PLAN.json') -Raw | ConvertFrom-Json
$roots=@('D:\aaa\GameCam-VO\','D:\aaa\GameCam-VO-TASK009\','D:\aaa\GameCam-VO-TASK010-A\')
foreach($target in $plan.targets){
    $absolute=[IO.Path]::GetFullPath([string]$target.path)
    if(-not ($roots | Where-Object {$absolute.StartsWith($_,[StringComparison]::OrdinalIgnoreCase)}) -or $absolute -match 'VIPER'){throw 'Out of exact retired-entry scope.'}
    if((Resolve-Path -LiteralPath $absolute).ProviderPath -ne $absolute){throw 'Resolved path mismatch.'}
    if((Get-Item -LiteralPath $absolute -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Unexpected junction.'}
    foreach($file in $target.files){if((Get-FileHash -LiteralPath $file.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256){throw 'Supplementary file identity changed.'}}
}
foreach($target in $plan.targets){
    if($target.kind -eq 'directory'){Remove-Item -LiteralPath $target.path -Recurse -Force}
    else{Remove-Item -LiteralPath $target.path -Force}
    if(Test-Path -LiteralPath $target.path){throw 'Retired entry still exists.'}
}
@{status='PASS';targets=@($plan.targets).Count;files=@($plan.targets.files).Count;retired_entries_absent=$true} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $audit 'SUPPLEMENTARY_RECEIPT.json') -Encoding utf8
Write-Output ('Removed retired status/config/result entries: '+@($plan.targets).Count)
