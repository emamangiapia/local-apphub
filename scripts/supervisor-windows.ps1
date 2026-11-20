# Supervisore Windows. Mantiene il server attivo e aggiorna solo via fast-forward.
param([Parameter(Mandatory=$true)][string]$SourceDir)

$ErrorActionPreference = 'Stop'
$source = (Resolve-Path $SourceDir).Path
$dataDir = Join-Path $env:LOCALAPPDATA 'LocalAppHub'
$logFile = Join-Path $dataDir 'supervisor.log'
$python = (& py -3 -c 'import sys; print(sys.executable)').Trim()
$child = $null

function Write-AppHubLog([string]$Message) {
    $line = '{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -Path $logFile -Value $line
}

Write-AppHubLog 'Supervisore avviato.'
while ($true) {
    try {
        # Non alterare file modificati dall'utente; non usare reset --hard.
        $dirty = & git -C $source status --porcelain
        if ($LASTEXITCODE -ne 0) { throw 'Checkout Git non disponibile' }
        if (-not $dirty) {
            & git -C $source fetch --quiet origin main
            if ($LASTEXITCODE -ne 0) { throw 'Fetch del controller non riuscito' }
            $current = (& git -C $source rev-parse HEAD).Trim()
            $latest = (& git -C $source rev-parse refs/remotes/origin/main).Trim()
            if ($current -ne $latest) {
                & git -C $source merge-base --is-ancestor $current $latest
                if ($LASTEXITCODE -ne 0) { throw 'Aggiornamento non fast-forward: richiesta verifica manuale' }
                & git -C $source merge --ff-only origin/main
                if ($LASTEXITCODE -ne 0) { throw 'Aggiornamento controller fallito' }
                Write-AppHubLog 'Controller aggiornato. Riavvio processo.'
                if ($null -ne $child -and -not $child.HasExited) {
                    Stop-Process -Id $child.Id -Force
                    $child.WaitForExit()
                }
                $child = $null
            }
        } else {
            Write-AppHubLog 'Aggiornamento sospeso: modifiche locali nella sorgente.'
        }
    } catch {
        Write-AppHubLog ('Controllo aggiornamenti: ' + $_.Exception.Message)
    }

    try {
        if ($null -eq $child -or $child.HasExited) {
            $child = Start-Process -FilePath $python -ArgumentList @('-m', 'apphub', 'serve') -WorkingDirectory $source -PassThru -WindowStyle Hidden
            Write-AppHubLog ('Server dashboard avviato (PID ' + $child.Id + ').')
        }
    } catch {
        Write-AppHubLog ('Avvio dashboard: ' + $_.Exception.Message)
    }
    Start-Sleep -Seconds 60
}
