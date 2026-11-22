# kit/github/

Reference files for build step B5 and for B1. The ignore file is always used; the pre-commit
hook, the README and the workflows only when the user wants them.

| File | Becomes | Notes |
|---|---|---|
| `gitignore.template` | `.gitignore` | Remove the `/wiki/` line when the wiki lives in the workspace repo (answer E4 = b) |
| `pre-commit` | `.githooks/pre-commit` | Enable with `git config core.hooksPath .githooks` |
| `gitattributes.template` | `.gitattributes` | Goes with the pre-commit hook: keeps its line endings right on Windows |
| `README.template.md` | `README.md` | Plain or styled per E6; no personal details |
| `workflows/gitleaks.yml` | `.github/workflows/gitleaks.yml` | Secret scan of the full history on GitHub |
| `workflows/checks.yml` | `.github/workflows/checks.yml` | Only when the workspace has checks worth running in CI |
| `dependabot.yml` | `.github/dependabot.yml` | Keeps workflow actions up to date |

Before use, check the current major versions of the actions on their release pages; the versions
here were current on 2026-11-21.
