# Auto Push Workflow

The repository is configured to use `.githooks/` as the local git hooks path.

The `post-commit` hook attempts to run:

```bash
git push origin HEAD:<current-branch>
```

## Requirements

1. A GitHub remote named `origin`
2. Git credentials already authenticated on the machine
3. Network access

## Setup

If this repo has no remote yet:

```powershell
git remote add origin <github-repo-url>
git push -u origin main
```

After the first push, future commits should push automatically.

## Disable Temporarily

PowerShell:

```powershell
$env:DISABLE_AUTO_PUSH="1"
```

Unset:

```powershell
Remove-Item Env:\DISABLE_AUTO_PUSH
```

## Important

Auto-push is intentionally commit-based. It does not push every file save.

This keeps GitHub history reviewable and prevents accidental upload of incomplete local edits.

