# Local AppHub by iPhone Facile. Eseguire dal clone pubblico con PowerShell.
param([switch]$NoScheduledTask, [switch]$NoOpenBrowser)

$ErrorActionPreference = 'Stop'
$sourceDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dataDir = Join-Path $env:LOCALAPPDATA 'LocalAppHub'
$supervisor = Join-Path $sourceDir 'scripts\supervisor-windows.ps1'
$taskName = 'iPhoneFacile-LocalAppHub'

foreach ($program in @('git', 'py')) {
    if (-not (Get-Command $program -ErrorAction SilentlyContinue)) {
        throw "Manca $program. Installa Git e Python 3.11+ prima di continuare."
    }
}
& py -3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ richiesto"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ richiesto' }

$composeAvailable = $false
if (Get-Command docker -ErrorAction SilentlyContinue) {
    & docker compose version
    $composeAvailable = ($LASTEXITCODE -eq 0)
}
if (-not $composeAvailable) {
    Write-Warning 'Motore container non ancora configurato. Consigliato Rancher Desktop con Moby/dockerd e Docker Compose. Puoi completare la configurazione dopo aver aperto la dashboard.'
}

if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
}
if (-not $NoScheduledTask) {
    $userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $supervisor + '" -SourceDir "' + $sourceDir + '"'
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
    $principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Local AppHub: aggiorna il controller e sincronizza le app ad ogni accesso Windows.' -Force | Out-Null
    Start-ScheduledTask -TaskName $taskName
    Write-Host "Attivita pianificata creata: $taskName (avvio al login Windows)."
} else {
    Write-Host 'Attivita pianificata non creata, per scelta.'
}

Write-Host ''
Write-Host 'Local AppHub installato.' -ForegroundColor Green
Write-Host 'Dashboard: http://127.0.0.1:8766'
Write-Host "Dati personali: $dataDir"
Write-Host 'Apri la dashboard: al primo accesso potrai creare la password, configurare le repository e aggiungere app dalla GUI.'
Write-Host 'Per avviare container: installa Rancher Desktop con motore Moby/dockerd (oppure Docker Desktop) e avvialo.'
Write-Host 'NOTA: il supervisore si avvia dopo il login Windows.'
if (-not $NoScheduledTask -and -not $NoOpenBrowser) {
    Start-Sleep -Seconds 2
    Start-Process 'http://127.0.0.1:8766'
}
