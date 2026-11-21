<!-- Title: `Prefix: what it does`, at most 70 characters. Prefixes: Add, Update, Fix, Refactor, Docs, Release. -->

## What and why

<!-- What changes, and why. Closes #... -->

## Type

- [ ] Add: something new
- [ ] Update: a change to something that exists
- [ ] Fix: a bug
- [ ] Refactor: same behaviour, different shape
- [ ] Docs: documentation only

## For existing workspaces

<!-- What does this mean for someone who already built a workspace? "Nothing" is a fine answer. -->

## Checklist

- [ ] Against `develop` (only `release/*` and `hotfix/*` go to `main`)
- [ ] `uv run --project kit/scripts pytest -q kit/scripts/tests` passes, with a test where code changed
- [ ] A line under `## [Unreleased]` in `CHANGELOG.md`, and under `### For your workspace` if users will notice
- [ ] A change to `SETUP.md` keeps section 7 and Appendix B complete
- [ ] No personal names, paths, IPs, customer data or secrets
