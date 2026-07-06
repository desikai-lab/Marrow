# run_ci.ps1 — Single entry point for all local CI checks.
# Usage (from marrow_server/ directory):
#   .\scripts\run_ci.ps1              # full suite
#   .\scripts\run_ci.ps1 -TestPath tests/unit/tools/test_artifacts.py  # single file
#   .\scripts\run_ci.ps1 -SkipTests  # lint + format only

param(
    [string]$TestPath = "tests",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$ruffConfig = "--config pyproject.toml"
$ruffTargets = "..\marrow_server ..\marrow_worker ..\marrow_common"

Write-Host ""
Write-Host "=== [1/4] ruff check --fix (auto-fix) ===" -ForegroundColor Cyan
Invoke-Expression "python -m ruff check --fix $ruffConfig $ruffTargets"
# --fix exits 0 if no unfixable errors remain; non-zero means unfixable errors exist
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: ruff check found unfixable errors." -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green

Write-Host ""
Write-Host "=== [2/4] ruff format (auto-format) ===" -ForegroundColor Cyan
Invoke-Expression "python -m ruff format $ruffConfig $ruffTargets"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: ruff format failed." -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green

Write-Host ""
Write-Host "=== [3/4] ruff check (verify clean) ===" -ForegroundColor Cyan
Invoke-Expression "python -m ruff check $ruffConfig $ruffTargets"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: ruff check still has errors after auto-fix (manual fix required)." -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green

if (-not $SkipTests) {
    Write-Host ""
    Write-Host "=== [4/4] pytest $TestPath ===" -ForegroundColor Cyan
    # pythonpath = ["src"] is configured in pyproject.toml — no env var needed
    python -m pytest $TestPath -v
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: tests failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "OK" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "=== [4/4] pytest SKIPPED ===" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
