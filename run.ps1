param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Run .\setup.ps1 first.'
}

& $python -m ipad_hybrid_control.cli --config (Join-Path $PSScriptRoot 'config.toml') @CommandArgs
exit $LASTEXITCODE
