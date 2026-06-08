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

Invoke-NekoCheck "Agent registry fast path" `
    ".\neko-core.ps1 --agents; .\neko-core.ps1 --agent task-resolver" `
    {
        & ".\neko-core.ps1" --agents
        & ".\neko-core.ps1" --agent "task-resolver"
    }

Invoke-NekoCheck "Tool registry fast path" `
    ".\neko-core.ps1 --tools; .\neko-core.ps1 --tool web-research" `
    {
        & ".\neko-core.ps1" --tools
        & ".\neko-core.ps1" --tool "web-research"
    }

Invoke-NekoCheck "Command registry fast path" `
    ".\neko-core.ps1 --commands; .\neko-core.ps1 --command run" `
    {
        & ".\neko-core.ps1" --commands
        & ".\neko-core.ps1" --command "run"
    }

Invoke-NekoCheck "Policy audit fast path" `
    ".\neko-core.ps1 --policy" `
    { & ".\neko-core.ps1" --policy }

Invoke-NekoCheck "Model inventory fast path without API key" `
    ".\neko-core.ps1 --model-inventory --run-dir run-model-inventory with NVIDIA_API_KEY cleared" `
    {
        $previousKey = $env:NVIDIA_API_KEY
        try {
            $env:NVIDIA_API_KEY = ""
            & ".\neko-core.ps1" --model-inventory --run-dir "run-model-inventory"
            if (-not (Test-Path -LiteralPath "run-model-inventory\model-inventory.txt")) {
                throw "missing model inventory report"
            }
        } finally {
            $env:NVIDIA_API_KEY = $previousKey
        }
    }

Invoke-NekoCheck "Unknown workflow returns friendly CLI error" `
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\neko-core.ps1 --workflow missing-workflow --output-dir output-verify-missing --limit 1" `
    { & powershell -NoProfile -ExecutionPolicy Bypass -File ".\neko-core.ps1" --workflow "missing-workflow" --output-dir "output-verify-missing" --limit 1 } `
    @(2)

if ($InputPath -and (Test-Path -LiteralPath $InputPath)) {
    Invoke-NekoCheck "Quick workflow produces pred.csv" `
        ".\neko-core.ps1 --workflow quick-dry-run --input `"$InputPath`" --output-dir output-verify --trace-dir traces-verify --limit 3" `
        { & ".\neko-core.ps1" --workflow "quick-dry-run" --input $InputPath --output-dir "output-verify" --trace-dir "traces-verify" --limit 3 }

    Invoke-NekoCheck "Run session writes output trace and report" `
        ".\neko-core.ps1 --workflow quick-dry-run --input `"$InputPath`" --run-dir run-verify --limit 3" `
        {
            & ".\neko-core.ps1" --workflow "quick-dry-run" --input $InputPath --run-dir "run-verify" --limit 3
            if (-not (Test-Path -LiteralPath "run-verify\output\pred.csv")) { throw "missing run output" }
            if (-not (Test-Path -LiteralPath "run-verify\traces\predictions.trace.jsonl")) { throw "missing run trace" }
            if (-not (Test-Path -LiteralPath "run-verify\run-report.md")) { throw "missing run report" }
            if (-not (Test-Path -LiteralPath "run-verify\review-tasks.md")) { throw "missing review tasks markdown" }
            if (-not (Test-Path -LiteralPath "run-verify\review-tasks.json")) { throw "missing review tasks json" }
            if (-not (Test-Path -LiteralPath "run-verify\events.jsonl")) { throw "missing event log" }
            Get-Content -LiteralPath "run-verify\run-report.md" -TotalCount 20
        }

    Invoke-NekoCheck "Session commands read resume-ready run artifacts" `
        ".\neko-core.ps1 --list-runs --runs-root .; .\neko-core.ps1 --session run-verify; .\neko-core.ps1 --events run-verify" `
        {
            & ".\neko-core.ps1" --list-runs --runs-root "."
            & ".\neko-core.ps1" --session "run-verify"
            & ".\neko-core.ps1" --events "run-verify"
        }

    Invoke-NekoCheck "Review task queue reads quick workflow artifacts" `
        ".\neko-core.ps1 --review-tasks run-verify\traces --run-dir run-review-tasks" `
        {
            & ".\neko-core.ps1" --review-tasks "run-verify\traces" --run-dir "run-review-tasks"
            if (-not (Test-Path -LiteralPath "run-review-tasks\review-tasks.md")) { throw "missing review task queue" }
        }

    Invoke-NekoCheck "Task resolver reruns qid-scoped review tasks" `
        ".\scripts\resolve-tasks.ps1 -TaskPath run-verify\review-tasks.json -InputPath `"$InputPath`" -Workflow quick-dry-run" `
        {
            & powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\resolve-tasks.ps1" `
                -TaskPath "run-verify\review-tasks.json" `
                -InputPath $InputPath `
                -Workflow "quick-dry-run"
            $latestTaskRun = Get-ChildItem -Directory "task-runs" |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First 1
            if (-not $latestTaskRun) { throw "missing task resolution run" }
            if (-not (Test-Path -LiteralPath (Join-Path $latestTaskRun.FullName "task-resolution.json"))) {
                throw "missing task resolution json"
            }
            if (-not (Test-Path -LiteralPath (Join-Path $latestTaskRun.FullName "comparison.txt"))) {
                throw "missing scoped comparison"
            }
        }

    Invoke-NekoCheck "Trace reviewer reads quick workflow artifacts" `
        ".\neko-core.ps1 --review-trace traces-verify" `
        { & ".\neko-core.ps1" --review-trace "traces-verify" }

    Invoke-NekoCheck "Run manifest is written with hashes" `
        "$pythonExe -c `"import json; m=json.load(open('traces-verify/run-manifest.json', encoding='utf-8')); assert m['schema_version']=='neko_core.run_manifest.v1'; assert len(m['input_sha256'])==64; print(m['workflow'], m['model'])`"" `
        { & $pythonExe -c "import json; m=json.load(open('traces-verify/run-manifest.json', encoding='utf-8')); assert m['schema_version']=='neko_core.run_manifest.v1'; assert len(m['input_sha256'])==64; print(m['workflow'], m['model'])" }

    Invoke-NekoCheck "Trace comparison reads identical run artifacts" `
        ".\neko-core.ps1 --compare-traces traces-verify traces-verify" `
        { & ".\neko-core.ps1" --compare-traces "traces-verify" "traces-verify" }
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
