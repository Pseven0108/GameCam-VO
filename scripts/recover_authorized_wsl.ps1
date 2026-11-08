# User-authorized recovery of the only registered WSL distribution, Ubuntu.
# No driver, WSL configuration, dataset or environment files are changed.
param([switch]$ForceStuckService)
$ErrorActionPreference = 'Stop'
$taskRoot = 'D:\aaa\GameCam-VO'
$taskStatus = Join-Path $taskRoot 'logs\E9_elevated_wsl_recovery_status.json'
if ($ForceStuckService) { $taskStatus = Join-Path $taskRoot 'logs\E9_elevated_wsl_force_recovery_status.json' }
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-RecoveryState($state) {
    $state | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $taskStatus -Encoding UTF8
}

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Windows administrator token is required to restart WslService.'
    }
    $distributions = @(Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' |
        ForEach-Object { (Get-ItemProperty -LiteralPath $_.PSPath).DistributionName })
    if ($distributions.Count -ne 1 -or $distributions[0] -ne 'Ubuntu') {
        throw 'Recovery scope changed: expected only the Ubuntu distribution.'
    }
    Write-RecoveryState @{status='RESTARTING_WSL_SERVICE'; user_authorized=$true; distribution='Ubuntu'; time=(Get-Date).ToUniversalTime().ToString('o')}
    if ($ForceStuckService) {
        $serviceDetail = (& "$env:SystemRoot\System32\sc.exe" queryex WslService) -join "`n"
        if ($serviceDetail -notmatch 'STATE\s*:\s*3\s+STOP_PENDING') {
            throw 'Force recovery is restricted to the recorded STOP_PENDING service.'
        }
        $taskServiceProcessId = [int]([regex]::Match($serviceDetail, 'PID\s*:\s*(\d+)').Groups[1].Value)
        if ($taskServiceProcessId -le 4) { throw 'Invalid dedicated WSL service process id.' }
        $taskServiceProcess = Get-Process -Id $taskServiceProcessId -ErrorAction Stop
        if ($taskServiceProcess.ProcessName -ne 'wslservice') { throw 'The selected process is not wslservice.' }
        Write-RecoveryState @{status='ENDING_STUCK_DEDICATED_WSL_SERVICE'; process_id=$taskServiceProcessId; user_authorized=$true; time=(Get-Date).ToUniversalTime().ToString('o')}
        Stop-Process -Id $taskServiceProcessId -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 1000
        Start-Service -Name WslService -ErrorAction Stop
    } else {
        Restart-Service -Name WslService -Force -ErrorAction Stop
    }
    $service = Get-Service WslService
    Write-RecoveryState @{status='WSL_SERVICE_RESTARTED'; service_status=$service.Status.ToString(); user_authorized=$true; distribution='Ubuntu'; time=(Get-Date).ToUniversalTime().ToString('o')}
} catch {
    Write-RecoveryState @{status='WSL_SERVICE_RECOVERY_FAILED'; error=$_.Exception.Message; error_id=$_.FullyQualifiedErrorId; time=(Get-Date).ToUniversalTime().ToString('o')}
    exit 1
}
