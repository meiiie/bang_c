param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$ErrorActionPreference = "Stop"
$entrypoint = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "neko-core.ps1"
& $entrypoint @CliArgs
exit $LASTEXITCODE
