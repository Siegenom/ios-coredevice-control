param(
    [string]$Python = "py"
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$venv = Join-Path $root '.venv'

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python command was not found: $Python"
}

$pythonArgs = @()
if ($Python -eq 'py') {
    $pythonArgs = @('-3.10')
}

$version = & $Python @pythonArgs -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $version.Trim() -ne '3.10') {
    throw "Python 3.10 is required. Install it, then run .\setup.ps1 or .\setup.ps1 -Python python when PATH resolves Python 3.10."
}

& $Python @pythonArgs -m venv $venv
if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
$venvPython = Join-Path $venv 'Scripts\python.exe'
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $venvPython -m pip install -e $root
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

function Test-SslPskNative([string]$PythonPath) {
    try {
        & $PythonPath -c "import sslpsk_pmd3.sslpsk" 2>$null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

if ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) {
    if (-not (Test-SslPskNative $venvPython)) {
        Write-Host "Repairing sslpsk-pmd3 OpenSSL DLL aliases."
        $basePrefix = (& $venvPython -c "import sys; print(sys.base_prefix)").Trim()
        $packageDir = (& $venvPython -c "import importlib.util; spec = importlib.util.find_spec('sslpsk_pmd3'); print(next(iter(spec.submodule_search_locations)))").Trim()
        $dllDir = Join-Path $basePrefix 'DLLs'
        $dllMap = @{
            'libssl-1_1.dll' = 'libssl-1_1-x64.dll'
            'libcrypto-1_1.dll' = 'libcrypto-1_1-x64.dll'
        }
        foreach ($sourceName in $dllMap.Keys) {
            $source = Join-Path $dllDir $sourceName
            $destination = Join-Path $packageDir $dllMap[$sourceName]
            if (-not (Test-Path -LiteralPath $source)) {
                throw "sslpsk-pmd3 requires OpenSSL 1.1 on Python 3.10, but $source was not found."
            }
            Copy-Item -LiteralPath $source -Destination $destination -Force
        }

        if (-not (Test-SslPskNative $venvPython)) {
            throw "sslpsk-pmd3 native dependency check failed after installing the Python 3.10 OpenSSL DLL aliases."
        }
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $root 'config.toml'))) {
    Copy-Item -LiteralPath (Join-Path $root 'config.example.toml') -Destination (Join-Path $root 'config.toml')
}

Write-Host 'Installed. Edit .\config.toml, then run:'
Write-Host "  .\run.ps1 doctor"
