# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Write kit/scripts/obsidian.lock.json: the plugin and theme versions a setup installs.

For every plugin and theme the kit configures, this reads the project's manifest at the head of
its repository (the version Obsidian itself would install), downloads that release's files and
records their SHA-256. `obsidian_setup.py` in a workspace installs exactly these files and
refuses anything else.

Run it when a plugin should move to a newer version, read the diff, and try the result in a
real vault before it goes into a release:

  uv run --script tools/obsidian_lock.py            rewrite the lock file
  uv run --script tools/obsidian_lock.py --check    exit 1 when upstream has newer versions

Not part of the kit: it never runs in a workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "kit" / "scripts" / "obsidian.lock.json"

# id (plugins) or folder name (themes) -> repository. The ids are the ones in
# kit/wiki/obsidian/community-plugins.json; a test keeps the two in step.
PLUGINS = {
    "obsidian-minimal-settings": "kepano/obsidian-minimal-settings",
    "templater-obsidian": "SilentVoid13/Templater",
    "notebook-navigator": "johansan/notebook-navigator",
    "obsidian-style-settings": "obsidian-community/obsidian-style-settings",
    "obsidian-meta-bind-plugin": "mProjectsCode/obsidian-meta-bind-plugin",
}
THEMES = {"Minimal": "kepano/obsidian-minimal"}
PLUGIN_FILES = ("main.js", "styles.css", "manifest.json")
THEME_FILES = ("theme.css", "manifest.json")
OPTIONAL = {"styles.css"}


def get(url: str) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": "nest-obsidian-lock"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def entry_for(key: str, repo: str, names: tuple[str, ...], id_field: str) -> dict:
    raw = get(f"https://raw.githubusercontent.com/{repo}/HEAD/manifest.json")
    if raw is None:
        raise SystemExit(f"{repo}: no manifest.json at HEAD")
    manifest = json.loads(raw)
    if manifest.get(id_field) != key:
        raise SystemExit(f"{repo}: manifest {id_field} is {manifest.get(id_field)!r}, expected {key!r}")
    version = manifest["version"]
    files: dict[str, dict] = {}
    for name in names:
        data = get(f"https://github.com/{repo}/releases/download/{version}/{name}")
        if data is None:
            if name in OPTIONAL:
                continue
            raise SystemExit(f"{repo} {version}: release has no {name}")
        files[name] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    released = json.loads(get(f"https://github.com/{repo}/releases/download/{version}/manifest.json"))
    if released.get("version") != version or released.get(id_field) != key:
        raise SystemExit(f"{repo} {version}: the released manifest does not match the repository's")
    return {
        "name": manifest.get("name", key),
        "repo": repo,
        "version": version,
        "minAppVersion": manifest.get("minAppVersion", ""),
        "files": files,
    }


def build() -> dict:
    return {
        "generated": date.today().isoformat(),
        "plugins": {key: entry_for(key, repo, PLUGIN_FILES, "id") for key, repo in PLUGINS.items()},
        "themes": {key: entry_for(key, repo, THEME_FILES, "name") for key, repo in THEMES.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare with upstream, write nothing")
    args = parser.parse_args()
    new = build()
    if args.check:
        old = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.is_file() else {}
        behind = [
            f"{kind[:-1]} {key}: {old.get(kind, {}).get(key, {}).get('version', 'none')} -> {entry['version']}"
            for kind in ("plugins", "themes")
            for key, entry in new[kind].items()
            if old.get(kind, {}).get(key, {}).get("version") != entry["version"]
        ]
        print("\n".join(behind) if behind else "The lock file is up to date.")
        return 1 if behind else 0
    LOCK.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for kind in ("plugins", "themes"):
        for key, entry in new[kind].items():
            print(f"{kind[:-1]:<7}{key:<28}{entry['version']:<10} needs Obsidian {entry['minAppVersion'] or '?'}")
    print(f"written: {LOCK.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
