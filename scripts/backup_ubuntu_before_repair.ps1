# Offline, read-only source capture before user-authorized conditional reinstall.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$taskRoot = 'D:\aaa\GameCam-VO'
$taskSource = 'C:\Users\Administrator\AppData\Local\Packages\CanonicalGroupLimited.UbuntuonWindows_79rhkp1fndgsc\LocalState\ext4.vhdx'
$taskStatusPath = Join-Path $taskRoot 'logs\WSL_ubuntu_backup_progress.json'
$taskRecord = @{status='STARTING'; source=$taskSource; time=(Get-Date).ToUniversalTime().ToString('o')}
$taskInputStream = $null
$taskOutputStream = $null
$taskHash = $null
function Save-TaskBackupState { $taskRecord | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $taskStatusPath -Encoding UTF8 }
try {
    $taskInfo = Get-Item -LiteralPath $taskSource
    $taskDrive = New-Object IO.DriveInfo('D')
    if ($taskDrive.AvailableFreeSpace -lt ($taskInfo.Length + 5GB)) {throw 'Insufficient D: free space for a verified complete backup.'}
    # Exclusive read handle refuses an active/mounted source rather than making
    # a potentially inconsistent live copy. Original VHD is never written.
    $taskInputStream = [IO.File]::Open($taskSource, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
    $taskHeader = New-Object byte[] 8
    if ($taskInputStream.Read($taskHeader, 0, 8) -ne 8 -or [Text.Encoding]::ASCII.GetString($taskHeader) -ne 'vhdxfile') {throw 'Source does not have a VHDX file header.'}
    $taskInputStream.Position = 0
    $taskStamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $taskBackupFolder = Join-Path $taskRoot ('data\recovery\Ubuntu-' + $taskStamp)
    [IO.Directory]::CreateDirectory($taskBackupFolder) | Out-Null
    $taskPartial = Join-Path $taskBackupFolder 'ext4.vhdx.part'
    $taskFinal = Join-Path $taskBackupFolder 'ext4.vhdx'
    $taskOutputStream = [IO.File]::Open($taskPartial, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    $taskHash = [Security.Cryptography.SHA256]::Create()
    $taskBuffer = New-Object byte[] (8MB)
    $taskCopied = 0L
    $taskLastReported = 0L
    $taskClock = [Diagnostics.Stopwatch]::StartNew()
    $taskRecord.status = 'COPYING_OFFLINE_EXCLUSIVE_SOURCE'
    $taskRecord.backup_folder = $taskBackupFolder
    $taskRecord.total_bytes = $taskInputStream.Length
    $taskRecord.source_modified_utc_at_capture = $taskInfo.LastWriteTimeUtc.ToString('o')
    $taskRecord.source_exclusive_read_lock = $true
    Save-TaskBackupState
    while (($taskCount = $taskInputStream.Read($taskBuffer, 0, $taskBuffer.Length)) -gt 0) {
        $taskOutputStream.Write($taskBuffer, 0, $taskCount)
        $taskHash.TransformBlock($taskBuffer, 0, $taskCount, $taskBuffer, 0) | Out-Null
        $taskCopied += $taskCount
        if ($taskCopied - $taskLastReported -ge 256MB) {
            $taskRecord.copied_bytes = $taskCopied
            $taskRecord.elapsed_seconds = $taskClock.Elapsed.TotalSeconds
            Save-TaskBackupState
            $taskLastReported = $taskCopied
        }
    }
    $taskHash.TransformFinalBlock([byte[]]@(), 0, 0) | Out-Null
    $taskSourceHash = [BitConverter]::ToString($taskHash.Hash).Replace('-', '').ToLowerInvariant()
    $taskOutputStream.Flush($true)
    $taskOutputStream.Dispose(); $taskOutputStream = $null
    $taskInputStream.Dispose(); $taskInputStream = $null
    $taskRecord.copied_bytes = $taskCopied
    $taskRecord.source_capture_sha256 = $taskSourceHash
    $taskRecord.status = 'VERIFYING_DESTINATION_FULL_SHA256'
    Save-TaskBackupState
    if ((Get-Item -LiteralPath $taskPartial).Length -ne $taskRecord.total_bytes) {throw 'Backup byte count mismatch.'}
    $taskDestinationHash = (Get-FileHash -LiteralPath $taskPartial -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($taskDestinationHash -ne $taskSourceHash) {throw 'Backup full SHA256 does not match source capture.'}
    Move-Item -LiteralPath $taskPartial -Destination $taskFinal -ErrorAction Stop
    $taskRecord.status = 'OFFLINE_VHD_BACKUP_SIZE_AND_SHA256_VERIFIED'
    $taskRecord.backup = $taskFinal
    $taskRecord.backup_sha256 = $taskDestinationHash
    $taskRecord.linux_filesystem_integrity = 'NOT_CHECKED; byte-identical offline source capture only'
    $taskRecord.elapsed_seconds = $taskClock.Elapsed.TotalSeconds
    $taskRecord | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $taskBackupFolder 'backup_manifest.json') -Encoding UTF8
    Save-TaskBackupState
} catch {
    $taskRecord.status = 'BACKUP_NOT_COMPLETED_OR_NOT_SAFE_TO_CAPTURE'
    $taskRecord.error = $_.Exception.Message
    $taskRecord.error_id = $_.FullyQualifiedErrorId
    Save-TaskBackupState
    exit 1
} finally {
    if ($taskInputStream) {$taskInputStream.Dispose()}
    if ($taskOutputStream) {$taskOutputStream.Dispose()}
    if ($taskHash) {$taskHash.Dispose()}
}
