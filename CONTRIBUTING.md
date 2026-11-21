# Contributing

Ideas, questions and bug reports are welcome as issues. Pull requests too. Everything in this
repo follows one set of templates, so the history reads the same from top to bottom.

**On this page:** [Setup](#setup) · [Branches](#branches) · [Commits and pull request titles](#commits-and-pull-request-titles) · [Pull requests](#pull-requests) · [Merging](#merging) · [Releases](#releases)

## Setup

```bash
git clone https://github.com/nickyjacobs/NEST.git
cd NEST
git switch develop
uv run --project kit/scripts pytest -q kit/scripts/tests
```

You need [uv](https://docs.astral.sh/uv/); it installs the right Python itself.

## Branches

| Branch | From | Into | What it is for |
|---|---|---|---|
| `main` | | | Released versions only. Every commit on `main` is a tagged release. |
| `develop` | `main` | `main`, through a release | Everything that is done and waiting for the next release. |
| `feature/<short-name>` | `develop` | `develop` | Something new: a skill, a setup step, a script. |
| `fix/<short-name>` | `develop` | `develop` | A fix that can wait for the next release. |
| `release/<x.y.z>` | `develop` | `main` | The last checks for a version: changelog, version numbers, a trial run. |
| `hotfix/<short-name>` | `main` | `main` | An urgent fix to a released version. |

Names are lowercase with hyphens: `feature/study-inbox`, `fix/windows-pre-commit`,
`release/1.1.0`. Nobody commits directly to `main` or `develop`.

## Commits and pull request titles

One format for both:

```
Prefix: what it does, in the imperative
```

| Prefix | Use it for |
|---|---|
| `Add:` | Something that was not there: a skill, a script, a setup step |
| `Update:` | A change to something that exists |
| `Fix:` | A bug |
| `Refactor:` | Same behaviour, different shape |
| `Docs:` | Documentation only |
| `Release:` | The merge of a release or hotfix into `main`, as `Release: v1.1.0` |

- At most 70 characters, no full stop at the end: `Add: study inbox skill`,
  `Fix: skip the file mode check on Windows`.
- The body is optional and says why, not what.
- No `--no-verify` and no force-push to `main` or `develop`.

## Pull requests

- One topic per pull request, against `develop`. Only `release/*` and `hotfix/*` go to `main`.
- Add a line under `## [Unreleased]` in `CHANGELOG.md`, in the section it belongs to. If the
  change reaches people who already have a workspace, say what it means for them under
  `### For your workspace`, in plain words.
- Run the tests: `uv run --project kit/scripts pytest -q kit/scripts/tests`.
- A change to `SETUP.md` keeps the answer routing table (section 7) and Appendix B complete.
- No personal names, paths, IPs, customer data or secrets in examples. Use placeholders
  (`<your-name>`, `<vault-path>`) and fictional people.

## Merging

| Pull request | Merge with | Result on the target branch |
|---|---|---|
| `feature/*` or `fix/*` into `develop` | Squash | One commit, titled like the pull request |
| `release/*` or `hotfix/*` into `main` | Merge commit | `Release: vX.Y.Z` |

The branch is deleted after the merge. After a release, `main` is merged back into `develop`.

## Releases

A release is a tag `vX.Y.Z` on `main` and a GitHub release named `NEST vX.Y.Z` whose text is
that version's block from `CHANGELOG.md`. The steps and the changelog template are in
[docs/project/releasing.md](docs/project/releasing.md).
