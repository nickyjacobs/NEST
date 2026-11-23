# The pictures in the getting-started guide

Real screenshots of VS Code with numbered marks on them. `shots.json` says, per picture, which
raw screenshot it starts from, what is cut off or covered, and where the marks go; `compose.py`
draws the result with headless Chrome into `assets/start/`.

```bash
cd assets/start/src
python3 compose.py              # every picture
python3 compose.py 6b-panel     # one
```

The raw screenshots live in `assets/start/raw/` and are not in the repository: an untouched
screenshot shows the maker's recent folders, trusted folders or account. Before a new one is
used, cover or crop everything that is not part of a fresh install, and write an example path
over a real one (`cover` and `labels` in `shots.json`).

How the screenshots are made: a VS Code profile with nothing in it (Profiles, New Profile,
every source set to None), the Claude Code extension as the only extension, the unpacked
release as the folder, and Claude Code in its default permission mode. Width 2000 pixels.
Retake them when VS Code or the extension changes what a beginner sees at these steps.

The pictures were made on macOS. A set made on Windows would be welcome.
