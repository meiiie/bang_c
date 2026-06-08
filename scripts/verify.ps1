param(
    [string]$InputPath,
    [switch]$Docker,
    [string]$Image = "neko-core:dev"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $repoRoot

$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonExe = "python"
}

$script:report = New-Object System.Collections.Generic.List[string]
$script:failed = $false
$script:partial = $false

function Add-ReportLine {
    param([string]$Line = "")
    $script:report.Add($Line) | Out-Null
}

function Invoke-NekoCheck {
    param(
        [string]$Name,
        [string]$CommandText,
        [scriptblock]$Command,
        [int[]]$ExpectedExitCodes = @(0)
    )

    Add-ReportLine "### Check: $Name"
    Add-ReportLine "**Command run:**"
    Add-ReportLine "  $CommandText"
    Add-ReportLine "**Output observed:**"

    $output = ""
    $exitCode = 0
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $global:LASTEXITCODE = 0
        $output = (
            & $Command 2>&1 | ForEach-Object {
                if ($_ -is [System.Management.Automation.ErrorRecord]) {
                    $_.Exception.Message
                } else {
                    $_.ToString()
                }
            } | Out-String
        ).TrimEnd()
        if ($null -ne $global:LASTEXITCODE) {
            $exitCode = [int]$global:LASTEXITCODE
        }
    } catch {
        $output = ($_ | Out-String).TrimEnd()
        $exitCode = 1
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ([string]::IsNullOrWhiteSpace($output)) {
        Add-ReportLine "  <no output>"
    } else {
        foreach ($line in ($output -split "`r?`n")) {
            Add-ReportLine "  $line"
        }
    }
    Add-ReportLine "  exit_code=$exitCode"

    if ($ExpectedExitCodes -contains $exitCode) {
        Add-ReportLine "**Result: PASS**"
    } else {
        Add-ReportLine "**Result: FAIL**"
        $script:failed = $true
    }
    Add-ReportLine ""
}

function Add-PartialCheck {
    param(
        [string]$Name,
        [string]$Reason
    )

    Add-ReportLine "### Check: $Name"
    Add-ReportLine "**Command run:**"
    Add-ReportLine "  <not run>"
    Add-ReportLine "**Output observed:**"
    Add-ReportLine "  $Reason"
    Add-ReportLine "**Result: PARTIAL**"
    Add-ReportLine ""
    $script:partial = $true
}

Add-ReportLine "# Neko Core Verification Report"
Add-ReportLine ""

Invoke-NekoCheck "Config JSON parses" `
    "$pythonExe -c `"import json; json.load(open('configs/default.json', encoding='utf-8')); print('config json ok')`"" `
    { & $pythonExe -c "import json; json.load(open('configs/default.json', encoding='utf-8')); print('config json ok')" }

Invoke-NekoCheck "Unit tests pass" `
    "$pythonExe -m unittest discover -s tests -v" `
    { & $pythonExe -m unittest discover -s tests -v }

Invoke-NekoCheck "Source compiles" `
    "$pythonExe -m compileall -q src" `
    { & $pythonExe -m compileall -q src }

Invoke-NekoCheck "CLI version fast path" `
    ".\neko-core.ps1 --version" `
    { & ".\neko-core.ps1" --version }

Invoke-NekoCheck "Workflow registry fast path" `
    ".\neko-core.ps1 --list-workflows" `
    { & ".\neko-core.ps1" --list-workflows }

Invoke-NekoCheck "Unknown workflow returns friendly CLI error" `
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\neko-core.ps1 --workflow missing-workflow --output-dir output-verify-missing --limit 1" `
    { & powershell -NoProfile -ExecutionPolicy Bypass -File ".\neko-core.ps1" --workflow "missing-workflow" --output-dir "output-verify-missing" --limit 1 } `
    @(2)

if ($InputPath -and (Test-Path -LiteralPath $InputPath)) {
    Invoke-NekoCheck "Quick workflow produces pred.csv" `
        ".\neko-core.ps1 --workflow quick-dry-run --input `"$InputPath`" --output-dir output-verify --trace-dir traces-verify --limit 3" `
        { & ".\neko-core.ps1" --workflow "quick-dry-run" --input $InputPath --output-dir "output-verify" --trace-dir "traces-verify" --limit 3 }

    Invoke-NekoCheck "Trace reviewer reads quick workflow artifacts" `
        ".\neko-core.ps1 --review-trace traces-verify" `
        { & ".\neko-core.ps1" --review-trace "traces-verify" }

    Invoke-NekoCheck "Run manifest is written with hashes" `
        "$pythonExe -c `"import json; m=json.load(open('traces-verify/run-manifest.json', encoding='utf-8')); assert m['schema_version']=='neko_core.run_manifest.v1'; assert len(m['input_sha256'])==64; print(m['workflow'], m['model'])`"" `
        { & $pythonExe -c "import json; m=json.load(open('traces-verify/run-manifest.json', encoding='utf-8')); assert m['schema_version']=='neko_core.run_manifest.v1'; assert len(m['input_sha256'])==64; print(m['workflow'], m['model'])" }
} else {
    Add-PartialCheck "Quick workflow produces pred.csv" "Input file not provided or not found. Pass -InputPath path\to\public_test.json."
}

if ($Docker) {
    Invoke-NekoCheck "Docker image builds" `
        "docker build -t $Image ." `
        { & docker build -t $Image . }

    if ($InputPath -and (Test-Path -LiteralPath $InputPath)) {
        Invoke-NekoCheck "Docker quick workflow writes /output/pred.csv" `
            "docker run --rm -v <temp-data>:/data -v <temp-output>:/output $Image --workflow quick-dry-run --limit 3" `
            {
                $base = Join-Path ([System.IO.Path]::GetTempPath()) "neko-core-verify-$([Guid]::NewGuid().ToString('N'))"
                $data = Join-Path $base "data"
                $out = Join-Path $base "output"
                New-Item -ItemType Directory -Path $data, $out | Out-Null
                Copy-Item -LiteralPath $InputPath -Destination (Join-Path $data "public_test.json")
                & docker run --rm -v "${data}:/data" -v "${out}:/output" $Image --workflow quick-dry-run --limit 3
                Get-Content -LiteralPath (Join-Path $out "pred.csv")
            }
    } else {
        Add-PartialCheck "Docker quick workflow writes /output/pred.csv" "Input file not provided or not found. Pass -InputPath path\to\public_test.json."
    }
}

if ($script:failed) {
    Add-ReportLine "VERDICT: FAIL"
    $script:report | ForEach-Object { Write-Output $_ }
    exit 1
}

if ($script:partial) {
    Add-ReportLine "VERDICT: PARTIAL"
    $script:report | ForEach-Object { Write-Output $_ }
    exit 2
}

Add-ReportLine "VERDICT: PASS"
$script:report | ForEach-Object { Write-Output $_ }
exit 0
