# run_ci.ps1 — Monorepo-level CI entry point: lint, format, and test all packages.
#
# Usage (from monorepo root D:\MCPs OR from any subfolder):
#   .\scripts\run_ci.ps1                                                   # full suite
#   .\scripts\run_ci.ps1 -TestPath marrow_server/tests/integration/mcp    # single dir
#   .\scripts\run_ci.ps1 -TestPath marrow_server/tests/unit/tools/test_artifacts.py  # single file
#   .\scripts\run_ci.ps1 -SkipTests                                        # lint + format only
#
# Ruff config source: marrow_server/pyproject.toml (canonical config for the monorepo)
# Pytest config source: marrow_server/pyproject.toml  (testpaths, pythonpath, markers)

param(
    [string]$TestPath = "tests",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

# Resolve monorepo root regardless of where the script is invoked from.
# Script lives at <monorepo_root>/scripts/run_ci.ps1, so parent of $PSScriptRoot = root.
$monorepoRoot     = Split-Path $PSScriptRoot -Parent
$marrowServerRoot = Join-Path $monorepoRoot "marrow_server"
$ruffConfig       = Join-Path $marrowServerRoot "pyproject.toml"

$ruffTargets = @(
    (Join-Path $monorepoRoot "marrow_server"),
    (Join-Path $monorepoRoot "marrow_worker"),
    (Join-Path $monorepoRoot "marrow_common")
) -join " "

Write-Host ""
Write-Host "=== [1/3] ruff check --fix (auto-fix) ===" -ForegroundColor Cyan
Invoke-Expression "python -m ruff check --fix --config `"$ruffConfig`" $ruffTargets"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: ruff check found unfixable errors." -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green

Write-Host ""
Write-Host "=== [2/3] ruff format (auto-format) ===" -ForegroundColor Cyan
Invoke-Expression "python -m ruff format --config `"$ruffConfig`" $ruffTargets"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: ruff format failed." -ForegroundColor Red
    exit 1
}

# Report any files that ruff modified so the developer can review and commit them.
# We do NOT auto-amend the git commit here — that is the developer's responsibility.
$dirty = git -C $monorepoRoot diff --name-only
if ($dirty) {
    Write-Host ""
    Write-Host "NOTE: ruff modified the following files. Review and commit them before pushing:" -ForegroundColor Yellow
    $dirty | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
} else {
    Write-Host "OK — no formatting changes." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== [3/3] ruff check (verify clean after auto-fix) ===" -ForegroundColor Cyan
Invoke-Expression "python -m ruff check --config `"$ruffConfig`" $ruffTargets"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: ruff check still has errors after auto-fix (manual fix required)." -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green

if (-not $SkipTests) {
    Write-Host ""
    Write-Host "=== [4/4] pytest $TestPath ===" -ForegroundColor Cyan
    # Run pytest from marrow_server/ so pyproject.toml [tool.pytest.ini_options] is found.
    # This sets pythonpath = ["src"] and testpaths = ["tests"] relative to marrow_server/.
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
