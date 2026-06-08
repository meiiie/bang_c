param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcPath = Join-Path $repoRoot "src"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonExe = "python"

if (Test-Path -LiteralPath $venvPython) {
    $pythonExe = $venvPython
}

if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$srcPath;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $srcPath
}

& $pythonExe -m hackaithon_c.run @CliArgs
exit $LASTEXITCODE
