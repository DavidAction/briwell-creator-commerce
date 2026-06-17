$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
    throw "This folder is not a git clone. Clone the GitHub repository first."
}

git -C $RepoRoot config core.hooksPath .githooks
Write-Host "Auto-push hook enabled for this clone."
Write-Host "Future commits will attempt to push to origin automatically."
