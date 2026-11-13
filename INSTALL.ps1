param()

$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

$Uv = Get-Command uv -ErrorAction SilentlyContinue
if ($null -eq $Uv) {
    throw "uv가 필요합니다. https://docs.astral.sh/uv/getting-started/installation/ 에서 설치한 뒤 다시 실행하세요."
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    & uv venv .venv --python 3.12
    if ($LASTEXITCODE -ne 0) { throw "프로젝트 가상환경 생성에 실패했습니다." }
}

& uv sync --frozen --no-dev
if ($LASTEXITCODE -ne 0) { throw "프로젝트 의존성 설치에 실패했습니다." }

& $Python -c "import fastapi, numpy, sklearn, torch, torchvision, uvicorn; print('설치 확인 완료:', torch.__version__)"
if ($LASTEXITCODE -ne 0) { throw "설치된 환경 검증에 실패했습니다." }
