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

function Invoke-NekoTextCommand {
    param(
        [string[]]$Arguments,
        [string]$OutputPath
    )

    $global:LASTEXITCODE = 0
    $output = (
        & ".\neko.ps1" @Arguments 2>&1 | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                $_.Exception.Message
            } else {
                $_.ToString()
            }
        } | Out-String
    ).TrimEnd()
    $exitCode = [int]$global:LASTEXITCODE
    Set-Content -LiteralPath $OutputPath -Value $output -Encoding UTF8
    return [pscustomobject]@{
        output = $output
        exit_code = $exitCode
    }
}

function Read-Verdict {
    param([string]$Text)

    if ($Text -match 'Verdict:\s*([A-Za-z]+)') {
        return $Matches[1].ToUpperInvariant()
    }
    return "UNKNOWN"
}

function Get-VerdictRank {
    param([string]$Verdict)

    switch ($Verdict) {
        "PASS" { return 0 }
        "WARN" { return 1 }
        "FAIL" { return 2 }
        default { return 3 }
    }
}

function Select-EvalCandidate {
    param([object[]]$Results)

    $ordered = @(
        $Results | Sort-Object `
            @{ Expression = { if ($_.valid) { 0 } else { 1 } }; Ascending = $true }, `
            @{ Expression = { [int]$_.changed_vs_first }; Ascending = $true }, `
            @{ Expression = { Get-VerdictRank $_.compare }; Ascending = $true }, `
            @{ Expression = { Get-VerdictRank $_.review }; Ascending = $true }, `
            @{ Expression = { [int]$_.fallbacks }; Ascending = $true }, `
            @{ Expression = { -[double]$_.score }; Ascending = $true }, `
            @{ Expression = { -[double]$_.confidence }; Ascending = $true }, `
            @{ Expression = { [string]$_.workflow }; Ascending = $true }, `
            @{ Expression = { [int]$_.run }; Ascending = $true }
    )
    if ($ordered.Count -eq 0) {
        return $null
    }
    return $ordered[0]
}

function Write-EvalArtifacts {
    param(
        [string]$RunDir,
        [string]$InputPath,
        [string[]]$Workflows,
        [int]$Limit,
        [int]$Repeat,
        [object[]]$Results,
        [object]$Candidate,
        [string]$Verdict,
        [string[]]$FailureReasons
    )

    $summaryPath = Join-Path $RunDir "eval-summary.json"
    $reportPath = Join-Path $RunDir "eval-report.md"
    $createdAt = (Get-Date).ToUniversalTime().ToString("o")

    [pscustomobject]@{
        schema_version = "neko_core.eval_summary.v1"
        created_at_utc = $createdAt
        input = $InputPath
        workflows = $Workflows
        limit = $Limit
        repeat = $Repeat
        verdict = $Verdict
        failure_reasons = $FailureReasons
        selected_candidate = $Candidate
        results = $Results
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# Neko Core Eval Report") | Out-Null
    $lines.Add("") | Out-Null
    $lines.Add("- Created UTC: $createdAt") | Out-Null
    $lines.Add("- Input: $InputPath") | Out-Null
    $lines.Add("- Workflows: $($Workflows -join ', ')") | Out-Null
    $lines.Add("- Limit: $Limit") | Out-Null
    $lines.Add("- Repeat: $Repeat") | Out-Null
    $lines.Add("- Verdict: $Verdict") | Out-Null
    if ($FailureReasons.Count -gt 0) {
        $lines.Add("- Failure reasons: $($FailureReasons -join ', ')") | Out-Null
    }
    if ($null -ne $Candidate) {
        $lines.Add(
            "- Selected candidate: $($Candidate.workflow) run $($Candidate.run) " +
            "($($Candidate.output))"
        ) | Out-Null
    }
    $lines.Add("") | Out-Null
    $lines.Add("| Workflow | Run | Valid | Score | Confidence | Fallbacks | Changed vs first | Review | Compare | Run report |") | Out-Null
    $lines.Add("| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- | --- |") | Out-Null
    foreach ($result in $Results) {
        $lines.Add(
            "| $($result.workflow) | $($result.run) | $($result.valid) | $($result.score) | $($result.confidence) | $($result.fallbacks) | $($result.changed_vs_first) | $($result.review) | $($result.compare) | $($result.run_report) |"
        ) | Out-Null
    }
    Set-Content -LiteralPath $reportPath -Value $lines -Encoding UTF8

    return [pscustomobject]@{
        summary = $summaryPath
        report = $reportPath
    }
}

$results = New-Object System.Collections.Generic.List[object]
$baselinePredictions = $null
$baselineTraceDir = $null

foreach ($workflow in $Workflows) {
    for ($iteration = 1; $iteration -le $Repeat; $iteration++) {
        $safeWorkflow = $workflow -replace '[^A-Za-z0-9_.-]', '_'
        $caseName = "$safeWorkflow-run$iteration"
        $caseDir = Join-Path $runDir $caseName
        $outputDir = Join-Path $caseDir "output"
        $traceDir = Join-Path $caseDir "traces"
        $runReportPath = Join-Path $caseDir "run-report.md"

        $commandText = ".\neko.ps1 --workflow $workflow --allow-development-workflow --input `"$InputPath`" --run-dir `"$caseDir`" --limit $Limit"
        Write-Output "Running: $commandText"
        & ".\neko.ps1" --workflow $workflow --allow-development-workflow --input $InputPath --run-dir $caseDir --limit $Limit
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
        if (-not (Test-Path -LiteralPath $runReportPath)) {
            throw "Missing run report: $runReportPath"
        }

        $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
        $predictions = Read-Predictions $predPath
        if ($null -eq $baselinePredictions) {
            $baselinePredictions = $predictions
        }
        if ($null -eq $baselineTraceDir) {
            $baselineTraceDir = $traceDir
        }
        $changed = Count-ChangedAnswers -Baseline $baselinePredictions -Current $predictions

        $reviewReportPath = Join-Path $caseDir "review.txt"
        $review = Invoke-NekoTextCommand `
            -Arguments @("--review-trace", $traceDir) `
            -OutputPath $reviewReportPath
        $reviewVerdict = Read-Verdict $review.output

        $compareReportPath = Join-Path $caseDir "compare-to-first.txt"
        $compare = Invoke-NekoTextCommand `
            -Arguments @("--compare-traces", $baselineTraceDir, $traceDir) `
            -OutputPath $compareReportPath
        $compareVerdict = Read-Verdict $compare.output

        $results.Add([pscustomobject]@{
            workflow = $workflow
            run = $iteration
            valid = [bool]$summary.valid
            total = [int]$summary.total_predictions
            score = [double]$summary.harness_score.total
            confidence = [double]$summary.average_confidence
            fallbacks = [int]$summary.fallbacks
            changed_vs_first = $changed
            review = $reviewVerdict
            compare = $compareVerdict
            output = $predPath
            trace = $traceDir
            run_report = $runReportPath
            review_report = $reviewReportPath
            compare_report = $compareReportPath
        }) | Out-Null
    }
}

Write-Output ""
Write-Output "Neko Core Eval Report"
Write-Output "Run directory: $runDir"
$results | Format-Table workflow, run, valid, total, score, confidence, fallbacks, changed_vs_first, review, compare -AutoSize | Out-String | Write-Output

$invalid = @($results | Where-Object { -not $_.valid })
$reviewFailures = @($results | Where-Object { $_.review -eq "FAIL" -or $_.review -eq "UNKNOWN" })
$comparisonFailures = @($results | Where-Object { $_.compare -eq "FAIL" -or $_.compare -eq "UNKNOWN" })
$unstable = @(
    $results |
        Group-Object workflow |
        Where-Object {
            $first = $_.Group[0].changed_vs_first
            ($_.Group | Where-Object { $_.changed_vs_first -ne $first }).Count -gt 0
        }
)

$failureReasons = New-Object System.Collections.Generic.List[string]
if ($invalid.Count -gt 0) {
    $failureReasons.Add("invalid_prediction_contract") | Out-Null
}
if ($reviewFailures.Count -gt 0) {
    $failureReasons.Add("trace_review_failed") | Out-Null
}
if ($comparisonFailures.Count -gt 0) {
    $failureReasons.Add("trace_comparison_failed") | Out-Null
}
if ($unstable.Count -gt 0) {
    $failureReasons.Add("workflow_changed_answer_instability") | Out-Null
}

$verdict = "PASS"
if ($failureReasons.Count -gt 0) {
    $verdict = "FAIL"
}

$candidate = Select-EvalCandidate -Results @($results | ForEach-Object { $_ })

$artifactPaths = Write-EvalArtifacts `
    -RunDir $runDir `
    -InputPath $InputPath `
    -Workflows $Workflows `
    -Limit $Limit `
    -Repeat $Repeat `
    -Results @($results | ForEach-Object { $_ }) `
    -Candidate $candidate `
    -Verdict $verdict `
    -FailureReasons @($failureReasons | ForEach-Object { $_ })

if ($null -ne $candidate) {
    Write-Output "Selected candidate: $($candidate.workflow) run $($candidate.run) -> $($candidate.output)"
}
Write-Output "Summary artifact: $($artifactPaths.summary)"
Write-Output "Report artifact: $($artifactPaths.report)"
Write-Output "EVAL VERDICT: $verdict"
if ($verdict -eq "FAIL") {
    exit 1
}
exit 0
