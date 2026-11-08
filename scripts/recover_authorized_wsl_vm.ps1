# Bounded recovery: only a single HCS utility VM explicitly owned by WSL.
# No VmCompute/Hyper-V service, driver, config, or other VM is restarted.
$ErrorActionPreference = 'Stop'
$taskRoot = 'D:\aaa\GameCam-VO'
$taskOutput = Join-Path $taskRoot 'logs\E9_elevated_wsl_vm_recovery.json'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$taskRecord = @{user_authorized=$true; time=(Get-Date).ToUniversalTime().ToString('o'); status='STARTED'}
function Save-Recovery { $taskRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskOutput -Encoding UTF8 }
try {
    $names = @(Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' | ForEach-Object {(Get-ItemProperty -LiteralPath $_.PSPath).DistributionName})
    if ($names.Count -ne 1 -or $names[0] -ne 'Ubuntu') {throw 'Expected only the authorized Ubuntu distribution.'}
    $inventoryLines = & "$env:SystemRoot\System32\hcsdiag.exe" list -raw 2>&1
    $inventoryCode = $LASTEXITCODE
    $inventoryText = $inventoryLines -join "`n"
    $inventoryText | Set-Content -LiteralPath (Join-Path $taskRoot 'logs\E9_elevated_hcs_inventory.json') -Encoding UTF8
    if ($inventoryCode -ne 0) {throw "HCS inventory failed: $inventoryCode"}
    $parsed = $inventoryText | ConvertFrom-Json
    if ($parsed -is [array]) { $systems = @($parsed) }
    elseif ($parsed.PSObject.Properties.Name -contains 'ComputeSystems') { $systems = @($parsed.ComputeSystems) }
    elseif ($parsed.PSObject.Properties.Name -contains 'Id') { $systems = @($parsed) }
    else {throw 'Unknown inventory schema; no VM will be stopped.'}
    $wslSystems = @($systems | Where-Object {$_.Owner -eq 'WSL' -and $_.SystemType -eq 'VirtualMachine'})
    if ($wslSystems.Count -ne 1) {throw 'Expected exactly one explicitly WSL-owned virtual machine; none stopped.'}
    $taskVmId = [guid]$wslSystems[0].Id
    $taskRecord.status = 'ENDING_ONLY_WSL_UTILITY_VM'
    $taskRecord.vm_id = $taskVmId.ToString()
    Save-Recovery
    $killOutput = & "$env:SystemRoot\System32\hcsdiag.exe" kill $taskVmId.ToString() 2>&1
    $taskRecord.kill_exit_code = $LASTEXITCODE
    $taskRecord.kill_output = $killOutput -join "`n"
    if ($taskRecord.kill_exit_code -ne 0) {throw 'HCS could not stop the WSL-owned utility VM.'}
    Start-Service -Name WslService -ErrorAction Stop
    $taskRecord.status = 'WSL_UTILITY_VM_STOPPED_SERVICE_STARTED'
    Save-Recovery
} catch {
    $taskRecord.status = 'SCOPED_WSL_VM_RECOVERY_FAILED'
    $taskRecord.error = $_.Exception.Message
    Save-Recovery
    exit 1
}
