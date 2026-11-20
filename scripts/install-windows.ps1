# Local AppHub by iPhone Facile. Eseguire dal clone pubblico con PowerShell.
param([switch]$NoScheduledTask)

$ErrorActionPreference = 'Stop'
$sourceDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dataDir = Join-Path $env:LOCALAPPDATA 'LocalAppHub'
$supervisor = Join-Path $sourceDir 'scripts\supervisor-windows.ps1'
$taskName = 'iPhoneFacile-LocalAppHub'

foreach ($program in @('git', 'py', 'docker')) {
    if (-not (Get-Command $program -ErrorAction SilentlyContinue)) {
        throw "Manca $program. Installa Git, Python 3.11+ e Docker Desktop prima di continuare."
    }
}
& py -3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ richiesto"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ richiesto' }
& docker compose version
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose v2 richiesto' }

if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
}
if (-not (Test-Path (Join-Path $dataDir 'auth.json'))) {
    Write-Host 'Impostazione password di accesso alla dashboard...'
    Push-Location $sourceDir
    try {
        & py -3 -m apphub init
        if ($LASTEXITCODE -ne 0) { throw 'Inizializzazione non riuscita' }
    } finally { Pop-Location }
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
Write-Host 'Per collegare un catalogo privato: py -3 -m apphub set-config --repo https://github.com/UTENTE/CONFIG-PRIVATA'
Write-Host 'NOTA: il servizio si avvia dopo il login Windows e richiede Docker Desktop in esecuzione.'
