param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [string[]]$Workflows = @("quick-dry-run"),
    [int]$Limit = 10,
    [int]$Repeat = 2,
    [string]$RunRoot = "eval-runs"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $repoRoot

if (-not (Test-Path -LiteralPath $InputPath)) {
    throw "InputPath not found: $InputPath"
}

if ($Repeat -lt 1) {
    throw "Repeat must be >= 1"
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $RunRoot $stamp
New-Item -ItemType Directory -Path $runDir | Out-Null

function Read-Predictions {
    param([string]$Path)

    $rows = Import-Csv -LiteralPath $Path
    $map = @{}
    foreach ($row in $rows) {
        $map[$row.qid] = $row.answer
    }
    return $map
}

function Count-ChangedAnswers {
    param(
        [hashtable]$Baseline,
        [hashtable]$Current
    )

    $changed = 0
    foreach ($qid in $Baseline.Keys) {
        if (-not $Current.ContainsKey($qid) -or $Current[$qid] -ne $Baseline[$qid]) {
            $changed += 1
        }
    }
    return $changed
}

$results = New-Object System.Collections.Generic.List[object]
$baselinePredictions = $null

foreach ($workflow in $Workflows) {
    for ($iteration = 1; $iteration -le $Repeat; $iteration++) {
        $safeWorkflow = $workflow -replace '[^A-Za-z0-9_.-]', '_'
        $caseName = "$safeWorkflow-run$iteration"
        $caseDir = Join-Path $runDir $caseName
        $outputDir = Join-Path $caseDir "output"
        $traceDir = Join-Path $caseDir "traces"

        New-Item -ItemType Directory -Path $outputDir, $traceDir | Out-Null

        $commandText = ".\neko-core.ps1 --workflow $workflow --input `"$InputPath`" --output-dir `"$outputDir`" --trace-dir `"$traceDir`" --limit $Limit"
        Write-Output "Running: $commandText"
        & ".\neko-core.ps1" --workflow $workflow --input $InputPath --output-dir $outputDir --trace-dir $traceDir --limit $Limit
        if ($LASTEXITCODE -ne 0) {
            throw "Workflow failed: $workflow run $iteration"
        }

        $summaryPath = Join-Path $traceDir "run-summary.json"
        $predPath = Join-Path $outputDir "pred.csv"
        if (-not (Test-Path -LiteralPath $summaryPath)) {
            throw "Missing run summary: $summaryPath"
        }
        if (-not (Test-Path -LiteralPath $predPath)) {
            throw "Missing predictions: $predPath"
        }

        $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
        $predictions = Read-Predictions $predPath
        if ($null -eq $baselinePredictions) {
            $baselinePredictions = $predictions
        }
        $changed = Count-ChangedAnswers -Baseline $baselinePredictions -Current $predictions

        $results.Add([pscustomobject]@{
            workflow = $workflow
            run = $iteration
            valid = [bool]$summary.valid
            total = [int]$summary.total_predictions
            score = [double]$summary.harness_score.total
            confidence = [double]$summary.average_confidence
            fallbacks = [int]$summary.fallbacks
            changed_vs_first = $changed
            output = $predPath
            trace = $traceDir
        }) | Out-Null
    }
}

Write-Output ""
Write-Output "Neko Core Eval Report"
Write-Output "Run directory: $runDir"
$results | Format-Table workflow, run, valid, total, score, confidence, fallbacks, changed_vs_first -AutoSize | Out-String | Write-Output

$invalid = @($results | Where-Object { -not $_.valid })
$unstable = @(
    $results |
        Group-Object workflow |
        Where-Object {
            $first = $_.Group[0].changed_vs_first
            ($_.Group | Where-Object { $_.changed_vs_first -ne $first }).Count -gt 0
        }
)

if ($invalid.Count -gt 0) {
    Write-Output "EVAL VERDICT: FAIL"
    exit 1
}

if ($unstable.Count -gt 0) {
    Write-Output "EVAL VERDICT: FAIL"
    exit 1
}

Write-Output "EVAL VERDICT: PASS"
exit 0
