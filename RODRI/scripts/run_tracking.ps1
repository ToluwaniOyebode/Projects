param(
    [Parameter(Mandatory=$true)][string]$VideoPath,
    [double]$StartSeconds = 0,
    [double]$DurationSeconds = 45,
    [ValidateSet("cpu","cuda","mps")][string]$Device = "cpu"
)
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Main = Join-Path $ProjectRoot "upstream\sports\examples\soccer\main.py"
$OutDir = Join-Path $ProjectRoot "outputs"
$ClipDir = Join-Path $OutDir "clips"
New-Item -ItemType Directory -Force -Path $OutDir,$ClipDir | Out-Null

if (-not (Test-Path $Py)) { throw "Virtual environment missing. Run .\RODRI\scripts\setup_windows.ps1 first." }
if (-not (Test-Path $Main)) { throw "Upstream main.py missing. Re-run setup." }
if (-not (Test-Path $VideoPath)) { throw "Video not found: $VideoPath" }
if ($StartSeconds -lt 0) { throw "StartSeconds must be non-negative." }
if ($DurationSeconds -le 0 -or $DurationSeconds -gt 180) { throw "DurationSeconds must be between 0 and 180 for the first test." }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw "FFmpeg is required for extracting a short clip." }

$Clip = Join-Path $ClipDir "rodri_test_clip.mp4"
& ffmpeg -hide_banner -loglevel error -ss $StartSeconds -i $VideoPath -t $DurationSeconds -an -c:v libx264 -preset veryfast -crf 23 -y $Clip
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Clip)) { throw "Clip extraction failed." }

$Result = Join-Path $OutDir "rodri_tracking_preview.mp4"
Push-Location (Split-Path $Main)
try {
    & $Py $Main --source_video_path $Clip --target_video_path $Result --device $Device --mode PLAYER_TRACKING
    if ($LASTEXITCODE -ne 0) { throw "Tracking pipeline failed. Read the upstream error above; run python main.py --help to check CLI changes." }
} finally {
    Pop-Location
}
Write-Host "Finished. Review output: $Result"
Write-Warning "Track IDs are not Rodri identity labels. Verify the correct player manually before training."
