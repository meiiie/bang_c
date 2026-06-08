param(
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $repoRoot

$venvDir = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv $venvDir
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip uninstall -y bang-c-harness | Out-Null
& $venvPython -m pip install -e .

$localShim = Join-Path $repoRoot "neko-core.ps1"

Write-Host "Installed Neko Core CLI in .venv."
Write-Host "Try: .\neko-core.ps1 --help"
Write-Host "Doctor: .\neko-core.ps1 --doctor"
Write-Host "Dry-run: .\neko-core.ps1 --input `"C:\Users\Admin\Downloads\public-test_1780368312.json`" --output-dir output --dry-run --limit 5"
if (Test-Path -LiteralPath $localShim) {
    Write-Host "Local shim: $localShim"
}
Write-Host "Compatibility alias remains available: .\bang-c.ps1"
Write-Host "The local shim uses .venv first, so it does not depend on your global PATH."
