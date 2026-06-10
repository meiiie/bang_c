param(
    [int] $MinMemoryGB = 48,
    [double] $BudgetUsd = 0,
    [int] $Limit = 12,
    [switch] $Json
)

$ErrorActionPreference = "Stop"

if (-not $env:RUNPOD_API_KEY) {
    throw "RUNPOD_API_KEY is required. Set it outside git before running this script."
}

$headers = @{
    Authorization = "Bearer $env:RUNPOD_API_KEY"
    "Content-Type" = "application/json"
}

$query = @"
query GpuTypes {
  myself { clientBalance currentSpendPerHr underBalance }
  gpuTypes {
    id
    displayName
    memoryInGb
    secureCloud
    communityCloud
    securePrice
    communityPrice
    secureSpotPrice
    communitySpotPrice
    maxGpuCount
    maxGpuCountSecureCloud
    maxGpuCountCommunityCloud
    throughput
  }
}
"@

$body = @{ query = $query } | ConvertTo-Json -Depth 4
$response = Invoke-RestMethod -Uri "https://api.runpod.io/graphql" -Method Post -Headers $headers -Body $body

if ($response.errors) {
    $message = ($response.errors | ConvertTo-Json -Depth 6)
    throw "RunPod GraphQL query failed: $message"
}

$account = $response.data.myself
$budget = if ($BudgetUsd -gt 0) { $BudgetUsd } else { [double] $account.clientBalance }

$rows = foreach ($gpu in $response.data.gpuTypes) {
    if ([int] $gpu.memoryInGb -lt $MinMemoryGB) {
        continue
    }

    $prices = @(
        @{ Kind = "community_spot"; Price = $gpu.communitySpotPrice; Available = [bool] $gpu.communityCloud },
        @{ Kind = "community"; Price = $gpu.communityPrice; Available = [bool] $gpu.communityCloud },
        @{ Kind = "secure_spot"; Price = $gpu.secureSpotPrice; Available = [bool] $gpu.secureCloud },
        @{ Kind = "secure"; Price = $gpu.securePrice; Available = [bool] $gpu.secureCloud }
    ) | Where-Object { $_.Available -and $_.Price -ne $null -and [double] $_.Price -gt 0 }

    if (-not $prices) {
        continue
    }

    $best = $prices | Sort-Object { [double] $_.Price } | Select-Object -First 1
    [pscustomobject] @{
        Name = $gpu.displayName
        MemoryGB = [int] $gpu.memoryInGb
        BestPriceKind = $best.Kind
        BestUsdHr = [math]::Round([double] $best.Price, 3)
        EstHoursAtBudget = if ($budget -gt 0) { [math]::Round($budget / [double] $best.Price, 2) } else { 0 }
        Community = [bool] $gpu.communityCloud
        Secure = [bool] $gpu.secureCloud
        MaxGpuCount = [int] $gpu.maxGpuCount
        MaxCommunity = [int] $gpu.maxGpuCountCommunityCloud
        MaxSecure = [int] $gpu.maxGpuCountSecureCloud
        Throughput = $gpu.throughput
    }
}

$shortlist = $rows | Sort-Object BestUsdHr, Name | Select-Object -First $Limit

if ($Json) {
    [pscustomobject] @{
        BalanceUsd = [math]::Round([double] $account.clientBalance, 3)
        CurrentSpendPerHr = [double] $account.currentSpendPerHr
        UnderBalance = [bool] $account.underBalance
        BudgetUsd = [math]::Round($budget, 3)
        MinMemoryGB = $MinMemoryGB
        Gpus = @($shortlist)
    } | ConvertTo-Json -Depth 8
    exit 0
}

Write-Host ("RunPod balance: {0} USD; current spend/hr: {1}" -f ([math]::Round([double] $account.clientBalance, 3)), $account.currentSpendPerHr)
Write-Host ("Shortlist: memory >= {0} GB, budget basis {1} USD" -f $MinMemoryGB, ([math]::Round($budget, 3)))
$shortlist | Format-Table -AutoSize
