param(
    [switch]$SkipDownload,
    [switch]$SkipTraining,
    [switch]$SkipPackage
)

$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "INSTALL.ps1")
if ($LASTEXITCODE -ne 0) { throw "환경 설치 단계가 실패했습니다." }
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Invoke-Python {
    param([string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python 단계가 실패했습니다: $($Arguments -join ' ')" }
}

Invoke-Python @("-m", "retina.bootstrap")
Invoke-Python @("-m", "retina.analysis", "trainLabels.csv", "outputs/assignment1")
Invoke-Python @("-m", "retina.cohort")

if (-not $SkipDownload) {
    Invoke-Python @("-m", "retina.download")
}
Invoke-Python @("-m", "retina.integrity")
if (-not $SkipTraining) {
    Invoke-Python @("-m", "retina.training", "--manifest", "data/manifest.csv", "--image-dir", "data/images", "--output-dir", "outputs/assignment2")
}
Invoke-Python @("-m", "retina.export_examples")

Invoke-Python @("-m", "retina.reports")
if (-not $SkipPackage) {
    Invoke-Python @("-m", "retina.package")
}
