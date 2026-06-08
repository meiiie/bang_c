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
& $venvPython -m pip install -e .

$localShim = Join-Path $repoRoot "bang-c.ps1"

Write-Host "Installed bang-c CLI in .venv."
Write-Host "Try: .\bang-c.ps1 --help"
Write-Host "Dry-run: .\bang-c.ps1 --input `"C:\Users\Admin\Downloads\public-test_1780368312.json`" --output-dir output --dry-run --limit 5"
if (Test-Path -LiteralPath $localShim) {
    Write-Host "Local shim: $localShim"
}
Write-Host "The local shim uses .venv first, so it does not depend on your global PATH."
