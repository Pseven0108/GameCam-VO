$ErrorActionPreference='Stop'
$auditRoot='D:\aaa\maintenance\VIPER_ONLY_THIRDPERSON_CLEANUP_20261127'
$python='D:\aaa\envs\gamecam-vo\python.exe'
& $python -u -B (Join-Path $auditRoot 'verify_cleanup.py') before
if($LASTEXITCODE -ne 0){throw 'Exact deletion identity checks did not pass.'}
$planPath=Join-Path $auditRoot 'EXTENDED_DELETION_PLAN.json'
$plan=Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
$check=Get-Content -LiteralPath (Join-Path $auditRoot 'PREDELETE_IDENTITY_CHECK.json') -Raw | ConvertFrom-Json
if($check.status -ne 'PASS' -or (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $check.plan_sha256){throw 'Deletion plan identity mismatch.'}
$resolvedTargets=@()
foreach($entry in $plan.targets){
    $absolute=[IO.Path]::GetFullPath([string]$entry.path)
    $insideProject=$absolute.StartsWith('D:\aaa\',[StringComparison]::OrdinalIgnoreCase)
    $inDownloads=([IO.Path]::GetDirectoryName($absolute) -eq 'C:\Users\Administrator\Downloads')
    if((-not $insideProject -and -not $inDownloads) -or $absolute -in @('D:\aaa','D:\aaa\GameCam-VO','D:\aaa\GameCam-VO-TASK009','D:\aaa\GameCam-VO-TASK010-A') -or $absolute -match 'VIPER'){throw 'Invalid final deletion boundary.'}
    $resolved=(Resolve-Path -LiteralPath $absolute).ProviderPath
    if($resolved -ne $absolute){throw 'Resolved target differs from exact plan.'}
    $item=Get-Item -LiteralPath $absolute -Force
    if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Top-level deletion target cannot be a junction.'}
    $resolvedTargets+=@{entry=$entry;absolute=$absolute}
}
# Remove only the directory aliases first. No shared Node runtime contents are
# traversed or deleted. PowerShell 7 removes a junction without -Recurse.
foreach($alias in $plan.junction_aliases){
    $path=[IO.Path]::GetFullPath([string]$alias.path)
    if(-not ($resolvedTargets | Where-Object {$path.StartsWith($_.absolute+'\',[StringComparison]::OrdinalIgnoreCase)})){throw 'Junction is outside exact experiment targets.'}
    $item=Get-Item -LiteralPath $path -Force
    if($item.LinkType -ne 'Junction' -or [string]$item.Target -ne [string]$alias.resolved_target){throw 'Shared junction identity changed.'}
    Remove-Item -LiteralPath $path -Force
    if(Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue){throw 'Junction alias was not removed.'}
    if($alias.target_exists_before -and -not (Test-Path -LiteralPath $alias.resolved_target)){throw 'Shared runtime target disappeared.'}
}
$journal=[Collections.Generic.List[object]]::new()
foreach($target in $resolvedTargets){
    $entry=$target.entry
    if($entry.kind -eq 'directory'){Remove-Item -LiteralPath $target.absolute -Recurse -Force}
    else{Remove-Item -LiteralPath $target.absolute -Force}
    if(Test-Path -LiteralPath $target.absolute){throw 'Deletion target still exists.'}
    $journal.Add([PSCustomObject]@{path=$target.absolute;logical_bytes=$entry.bytes;files=$entry.files;deleted_at=(Get-Date -Format o)})
    $journal | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $auditRoot 'DELETION_JOURNAL.json') -Encoding utf8
    Write-Output ('Removed '+$target.absolute)
}
& $python -u -B (Join-Path $auditRoot 'verify_cleanup.py') after
if($LASTEXITCODE -ne 0){throw 'Post-deletion protection checks require review.'}
Write-Output ('Completed exact cleanup targets: '+$journal.Count)
