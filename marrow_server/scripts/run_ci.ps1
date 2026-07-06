# run_ci.ps1 — Single entry point for all local CI checks.
# Usage (from marrow_server/ directory OR from monorepo root):
#   .\scripts\run_ci.ps1              # full suite
#   .\scripts\run_ci.ps1 -TestPath tests/unit/tools/test_artifacts.py  # single file
#   .\scripts\run_ci.ps1 -SkipTests  # lint + format only

param(
    [string]$TestPath = "tests",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

# Resolve monorepo root regardless of where the script is invoked from.
# The script lives at <marrow_server>/scripts/run_ci.ps1
# So the marrow_server root is always one directory above $PSScriptRoot.
$marrowServerRoot = Split-Path $PSScriptRoot -Parent
$monorepoRoot     = Split-Path $marrowServerRoot -Parent
$ruffConfig       = Join-Path $marrowServerRoot "pyproject.toml"

$ruffTargets = @(
    (Join-Path $monorepoRoot "marrow_server"),
    (Join-Path $monorepoRoot "marrow_worker"),
    (Join-Path $monorepoRoot "marrow_common")
) -join " "

Write-Host ""
Write-Host "=== [1/4] ruff check --fix (auto-fix) ===" -ForegroundColor Cyan
Invoke-Expression "python -m ruff check --fix --config `"$ruffConfig`" $ruffTargets"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: ruff check found unfixable errors." -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green

Write-Host ""
Write-Host "=== [2/4] ruff format (auto-format) ===" -ForegroundColor Cyan
Invoke-Expression "python -m ruff format --config `"$ruffConfig`" $ruffTargets"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: ruff format failed." -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green

Write-Host ""
Write-Host "=== [3/4] ruff check (verify clean) ===" -ForegroundColor Cyan
Invoke-Expression "python -m ruff check --config `"$ruffConfig`" $ruffTargets"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: ruff check still has errors after auto-fix (manual fix required)." -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green

if (-not $SkipTests) {
    Write-Host ""
    Write-Host "=== [4/4] pytest $TestPath ===" -ForegroundColor Cyan
    # Run pytest from the marrow_server root (where pyproject.toml lives)
    Push-Location $marrowServerRoot
    try {
        python -m pytest $TestPath -v
        if ($LASTEXITCODE -ne 0) {
            Write-Host "FAIL: tests failed." -ForegroundColor Red
            exit 1
        }
    } finally {
        Pop-Location
    }
    Write-Host "OK" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "=== [4/4] pytest SKIPPED ===" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
