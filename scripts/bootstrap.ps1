param(
    [switch]$SkipChecks
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $repoRoot

$venvDir = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python is required to install Neko Core. Install Python 3.10+ and rerun this script."
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    & $python.Source -m venv $venvDir
}

& $venvPython -m pip install --upgrade pip
$legacyPackage = & $venvPython -m pip list --format=freeze | Where-Object { $_ -match "^bang-c-harness==" }
if ($legacyPackage) {
    & $venvPython -m pip uninstall -y bang-c-harness | Out-Null
}
& $venvPython -m pip install -e .

$localShim = Join-Path $repoRoot "neko.ps1"

function Invoke-NekoCheck {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    Write-Host "Check: $Name"
    & $localShim @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Neko Core bootstrap check failed: $Name"
    }
}

if (-not $SkipChecks) {
    Invoke-NekoCheck "version" @("--version")
    Invoke-NekoCheck "doctor" @("--doctor")
    Invoke-NekoCheck "policy" @("--policy")
    Invoke-NekoCheck "workflows" @("--list-workflows")
}

Write-Host "Installed Neko Core CLI in .venv."
Write-Host "Try: .\neko.ps1 --help"
Write-Host "Doctor: .\neko.ps1 --doctor"
Write-Host "Init workspace config: .\neko.ps1 --init"
Write-Host "Dry-run: .\neko.ps1 --input `"C:\Users\Admin\Downloads\public-test_1780368312.json`" --output-dir output --dry-run --limit 5"
Write-Host "Skip install checks when needed: .\scripts\bootstrap.ps1 -SkipChecks"
if (Test-Path -LiteralPath $localShim) {
    Write-Host "Local shim: $localShim"
}
Write-Host "Compatibility aliases remain available: .\neko-core.ps1 and .\bang-c.ps1"
Write-Host "The local shim uses .venv first, so it does not depend on your global PATH."
