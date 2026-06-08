param(
    [string]$Source = "git+https://github.com/meiiie/bang_c.git"
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    $candidates = @(
        @{ Command = "py"; Args = @("-3.11") },
        @{ Command = "py"; Args = @("-3") },
        @{ Command = "python"; Args = @() },
        @{ Command = "python3"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate.Command -ErrorAction SilentlyContinue
        if (-not $command) {
            continue
        }

        $args = @()
        $args += $candidate.Args
        $args += @("-c", "import sys; print(str(sys.executable) + '|' + str(sys.version_info.major) + '.' + str(sys.version_info.minor))")
        try {
            $output = & $candidate.Command @args 2>$null
        } catch {
            continue
        }

        if (-not $output) {
            continue
        }

        $parts = "$output".Trim().Split("|")
        if ($parts.Length -ne 2) {
            continue
        }

        $version = [version]$parts[1]
        if ($version -ge [version]"3.11") {
            return @{
                Command = $candidate.Command
                Prefix = $candidate.Args
                Executable = $parts[0]
                Version = $parts[1]
            }
        }
    }

    throw "Python 3.11+ is required. Install Python 3.11+ and rerun this installer."
}

function Invoke-SelectedPython {
    param(
        [string[]]$Arguments
    )

    $fullArgs = @()
    $fullArgs += $script:Python.Prefix
    $fullArgs += $Arguments
    & $script:Python.Command @fullArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $($Arguments -join ' ')"
    }
}

$script:Python = Resolve-Python
Write-Host "Using Python $($script:Python.Version): $($script:Python.Executable)"

Write-Host "Installing/upgrading pipx..."
Invoke-SelectedPython -Arguments @("-m", "pip", "install", "--user", "--upgrade", "pipx")

Write-Host "Ensuring pipx app path is registered..."
Invoke-SelectedPython -Arguments @("-m", "pipx", "ensurepath")

$localBin = Join-Path $HOME ".local\bin"
if (Test-Path -LiteralPath $localBin) {
    $env:PATH = "$localBin;$env:PATH"
}

Write-Host "Installing Neko Core from $Source ..."
Invoke-SelectedPython -Arguments @("-m", "pipx", "install", "--force", $Source)

$candidateCommands = @(
    "neko-core",
    (Join-Path $localBin "neko-core.exe"),
    (Join-Path $localBin "neko-core.ps1"),
    (Join-Path $localBin "neko-core")
)

$verified = $false
foreach ($candidate in $candidateCommands) {
    if ($candidate -eq "neko-core") {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $command) {
            continue
        }
    } elseif (-not (Test-Path -LiteralPath $candidate)) {
        continue
    }

    Write-Host "Verifying $candidate --version"
    & $candidate --version
    if ($LASTEXITCODE -eq 0) {
        $verified = $true
        break
    }
}

if (-not $verified) {
    Write-Warning "Neko Core installed, but the command is not visible in this shell yet. Open a new terminal or add $localBin to PATH."
} else {
    Write-Host "Neko Core installed."
    Write-Host "Try: neko-core --doctor"
    Write-Host "Run: neko-core --workflow contest-strict --data-dir data --output-dir output"
}
