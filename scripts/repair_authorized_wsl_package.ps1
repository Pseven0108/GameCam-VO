# User authorized repair/reinstallation if restart does not recover WSL.
# Repair only the registered Microsoft WSL component. Never unregister Ubuntu.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$taskRoot = 'D:\aaa\GameCam-VO'
$taskStatus = Join-Path $taskRoot 'logs\WSL_component_repair_status.json'
$taskProduct = '{020F8AC8-A788-4E39-8E9B-8FECFA843632}'
$taskCache = 'C:\Windows\Installer\56f6f.msi'
$taskRecord = @{status='CHECKING_REPAIR_PREREQUISITES'; user_authorized=$true; time=(Get-Date).ToUniversalTime().ToString('o')}
function Save-RepairState { $taskRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskStatus -Encoding UTF8 }
try {
    Save-RepairState
    $taskBackup = Get-Content -LiteralPath (Join-Path $taskRoot 'logs\WSL_ubuntu_backup_progress.json') -Raw | ConvertFrom-Json
    if ($taskBackup.status -ne 'OFFLINE_VHD_BACKUP_SIZE_AND_SHA256_VERIFIED' -or $taskBackup.source_capture_sha256 -ne $taskBackup.backup_sha256) {
        throw 'Verified complete offline Ubuntu backup is required before repair.'
    }
    if ((Get-Item -LiteralPath $taskBackup.backup).Length -ne $taskBackup.total_bytes) {throw 'Verified backup file size changed.'}
    $taskInstalled = Get-ItemProperty -LiteralPath ('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\' + $taskProduct)
    if ($taskInstalled.DisplayName -ne 'Windows Subsystem for Linux' -or $taskInstalled.DisplayVersion -ne '2.7.12.0') {throw 'Installed WSL product changed; repair stopped.'}
    $taskSignature = Get-AuthenticodeSignature -LiteralPath $taskCache
    if ($taskSignature.Status -ne 'Valid' -or $taskSignature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') {
        throw 'The local WSL package does not have a valid Microsoft signature.'
    }
    $taskStamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $taskMsiLog = Join-Path $taskRoot ('logs\WSL_component_repair_' + $taskStamp + '.msi.log')
    $taskRecord.status = 'REPAIRING_EXISTING_MICROSOFT_WSL_PACKAGE'
    $taskRecord.product = $taskProduct
    $taskRecord.version = $taskInstalled.DisplayVersion
    $taskRecord.package_sha256 = (Get-FileHash -LiteralPath $taskCache -Algorithm SHA256).Hash.ToLowerInvariant()
    $taskRecord.microsoft_signature_valid = $true
    $taskRecord.ubuntu_backup = $taskBackup.backup
    $taskRecord.backup_sha256 = $taskBackup.backup_sha256
    $taskRecord.installer_log = $taskMsiLog
    $taskRecord.automatic_Windows_restart_disabled = $true
    $taskRecord.Ubuntu_unregistration_requested = $false
    Save-RepairState
    $taskInstallProcess = Start-Process -FilePath "$env:SystemRoot\System32\msiexec.exe" -ArgumentList @('/fa', $taskProduct, '/qn', '/norestart', '/L*v', $taskMsiLog) -WindowStyle Hidden -Wait -PassThru -ErrorAction Stop
    $taskRecord.exit_code = $taskInstallProcess.ExitCode
    if ($taskInstallProcess.ExitCode -eq 0) { $taskRecord.status = 'WSL_COMPONENT_REPAIR_COMPLETED' }
    elseif ($taskInstallProcess.ExitCode -eq 3010) { $taskRecord.status = 'WSL_COMPONENT_REPAIR_COMPLETED_WINDOWS_RESTART_REQUIRED' }
    else { $taskRecord.status = 'WSL_COMPONENT_REPAIR_FAILED' }
    Save-RepairState
} catch {
    $taskRecord.status = 'WSL_COMPONENT_REPAIR_FAILED'
    $taskRecord.error = $_.Exception.Message
    $taskRecord.error_id = $_.FullyQualifiedErrorId
    Save-RepairState
    exit 1
}
