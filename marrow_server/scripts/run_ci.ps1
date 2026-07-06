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

Write-Host ""
Write-Host "=== [1/3] ruff check ===" -ForegroundColor Cyan
python -m ruff check --config pyproject.toml ..\marrow_server ..\marrow_worker ..\marrow_common
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: ruff check found errors. Run: python -m ruff check --fix --config pyproject.toml <files>" -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green

Write-Host ""
Write-Host "=== [2/3] ruff format --check ===" -ForegroundColor Cyan
python -m ruff format --check --config pyproject.toml ..\marrow_server ..\marrow_worker ..\marrow_common
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: formatting issues found. Run: python -m ruff format --config pyproject.toml <files>" -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green

if (-not $SkipTests) {
    Write-Host ""
    Write-Host "=== [3/3] pytest $TestPath ===" -ForegroundColor Cyan
    # pythonpath = ["src"] is configured in pyproject.toml — no env var needed
    python -m pytest $TestPath -v
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: tests failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "OK" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "=== [3/3] pytest SKIPPED ===" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
