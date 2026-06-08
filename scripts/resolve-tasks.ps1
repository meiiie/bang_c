param(
    [Parameter(Mandatory = $true)]
    [string]$TaskPath,
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [string]$Workflow = "verify-all",
    [string]$RunRoot = "task-runs"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $repoRoot

if (-not (Test-Path -LiteralPath $TaskPath)) {
    throw "TaskPath not found: $TaskPath"
}
if (-not (Test-Path -LiteralPath $InputPath)) {
    throw "InputPath not found: $InputPath"
}

$payload = Get-Content -LiteralPath $TaskPath -Raw | ConvertFrom-Json
if ($payload.schema_version -ne "neko_core.review_tasks.v1") {
    throw "Unsupported task schema: $($payload.schema_version)"
}

$qids = @(
    $payload.tasks |
        Where-Object { $_.qid } |
        ForEach-Object { [string]$_.qid } |
        Select-Object -Unique
)

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $RunRoot $stamp
New-Item -ItemType Directory -Path $runDir | Out-Null

$reportPath = Join-Path $runDir "task-resolution-report.md"
$commandOutputPath = Join-Path $runDir "command-output.txt"

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Neko Core Task Resolution Report") | Out-Null
$lines.Add("") | Out-Null
$lines.Add("- Task file: $TaskPath") | Out-Null
$lines.Add("- Input: $InputPath") | Out-Null
$lines.Add("- Workflow: $Workflow") | Out-Null
$lines.Add("- Run directory: $runDir") | Out-Null
$lines.Add("- Qids: $($qids -join ', ')") | Out-Null

if ($qids.Count -eq 0) {
    $lines.Add("") | Out-Null
    $lines.Add("No qid-scoped tasks found.") | Out-Null
    Set-Content -LiteralPath $reportPath -Value $lines -Encoding UTF8
    Write-Output "Task resolution report: $reportPath"
    exit 0
}

$solveRunDir = Join-Path $runDir "resolution-run"
$arguments = @(
    "--workflow", $Workflow,
    "--input", $InputPath,
    "--run-dir", $solveRunDir
)
foreach ($qid in $qids) {
    $arguments += @("--qid", $qid)
}

$displayArguments = $arguments | ForEach-Object {
    $arg = [string]$_
    if ($arg -match "\s") {
        '"' + ($arg -replace '"', '\"') + '"'
    } else {
        $arg
    }
}
$commandText = ".\neko-core.ps1 " + ($displayArguments -join " ")
$lines.Add("- Command: $commandText") | Out-Null
$lines.Add("") | Out-Null

$global:LASTEXITCODE = 0
$output = (
    & ".\neko-core.ps1" @arguments 2>&1 | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) {
            $_.Exception.Message
        } else {
            $_.ToString()
        }
    } | Out-String
).TrimEnd()
$exitCode = [int]$global:LASTEXITCODE
Set-Content -LiteralPath $commandOutputPath -Value $output -Encoding UTF8

$predPath = Join-Path $solveRunDir "output\pred.csv"
$traceDir = Join-Path $solveRunDir "traces"
$runReportPath = Join-Path $solveRunDir "run-report.md"

$lines.Add("## Result") | Out-Null
$lines.Add("") | Out-Null
$lines.Add("- Exit code: $exitCode") | Out-Null
$lines.Add("- Predictions: $predPath") | Out-Null
$lines.Add("- Trace: $traceDir") | Out-Null
$lines.Add("- Run report: $runReportPath") | Out-Null
$lines.Add("- Command output: $commandOutputPath") | Out-Null
$lines.Add("") | Out-Null
$lines.Add("## Tasks") | Out-Null
$lines.Add("") | Out-Null
foreach ($task in $payload.tasks) {
    if (-not $task.qid) {
        continue
    }
    $priority = ([string]$task.priority).ToUpperInvariant()
    $lines.Add("- $priority $($task.task_id) [$($task.qid)]: $($task.recommended_action)") | Out-Null
}

Set-Content -LiteralPath $reportPath -Value $lines -Encoding UTF8
Write-Output "Task resolution report: $reportPath"
if ($exitCode -ne 0) {
    exit $exitCode
}
exit 0
