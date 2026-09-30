$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Run .\setup.ps1 first.'
}

Push-Location $PSScriptRoot
try {
    $sslpskOk = $true
    try {
        & $python -c "import sslpsk_pmd3.sslpsk" 2>$null
        $sslpskOk = $LASTEXITCODE -eq 0
    }
    catch {
        $sslpskOk = $false
    }
    if (-not $sslpskOk) {
        throw 'sslpsk-pmd3 native dependency check failed. Re-run .\setup.ps1.'
    }
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python .\tools\check_release.py
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
