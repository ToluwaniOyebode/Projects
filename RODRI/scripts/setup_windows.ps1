$ErrorActionPreference = "Stop"

# This script runs from the repository's RODRI folder.
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$UpstreamRoot = Join-Path $ProjectRoot "upstream\sports"
$SoccerDir = Join-Path $UpstreamRoot "examples\soccer"
$Venv = Join-Path $ProjectRoot ".venv"
$DataDir = Join-Path $SoccerDir "data"

foreach ($tool in @("python", "git")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Required command '$tool' not found. Install it and reopen PowerShell."
    }
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "FFmpeg not found in PATH. Install FFmpeg before running the tracking script."
}

if (-not (Test-Path $UpstreamRoot)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $UpstreamRoot) | Out-Null
    git clone https://github.com/roboflow/sports.git $UpstreamRoot
} else {
    Write-Host "Using existing upstream clone at $UpstreamRoot"
}

if (-not (Test-Path $Venv)) { python -m venv $Venv }
$Py = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"

& $Py -m pip install --upgrade pip wheel
& $Pip install git+https://github.com/roboflow/sports.git
& $Pip install -r (Join-Path $SoccerDir "requirements.txt")
& $Pip install gdown

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
$Weights = @(
    @{ Name = "football-ball-detection.pt"; Id = "1isw4wx-MK9h9LMr36VvIWlJD6ppUvw7V" },
    @{ Name = "football-player-detection.pt"; Id = "17PXFNlx-jI7VjVo_vQnB1sONjRyvoB-q" },
    @{ Name = "football-pitch-detection.pt"; Id = "1Ma5Kt86tgpdjCTKfum79YMgNnSjcoOyf" }
)
foreach ($W in $Weights) {
    $Out = Join-Path $DataDir $W.Name
    if ((Test-Path $Out) -and (Get-Item $Out).Length -gt 1000000) {
        Write-Host "Keeping existing model file: $($W.Name)"
        continue
    }
    & $Py -m gdown "https://drive.google.com/uc?id=$($W.Id)" -O $Out
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Out) -or (Get-Item $Out).Length -lt 1000000) {
        throw "Model download failed or appears incomplete: $($W.Name). Verify the upstream download URL."
    }
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Next: .\RODRI\scripts\run_tracking.ps1 -VideoPath 'C:\path\to\match.mp4' -StartSeconds 600 -DurationSeconds 45 -Device cpu"
