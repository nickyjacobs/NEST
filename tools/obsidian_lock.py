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
  uv run --script tools/obsidian_lock.py --check    exit 1 when the lock file differs from upstream

--check compares everything a fresh run would write except the date: the set of plugins and
themes, each name, repository and version, the Obsidian version each needs, and each file's
checksum. A release whose files were replaced under the
same version number shows up as a changed checksum.

Not part of the kit: it never runs in a workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "kit" / "scripts" / "obsidian.lock.json"

# id (plugins) or folder name (themes) -> repository, as Obsidian's own register lists them
# (community-plugins.json and community-css-themes.json in obsidianmd/obsidian-releases): check a
# new line against that register by hand. tools/tests/test_obsidian_lock.py keeps these tables in
# step with kit/wiki/obsidian/community-plugins.json and the theme in appearance.json.
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
MAX_BYTES = 40 * 1024 * 1024  # the same cap obsidian_setup.py downloads with
VERSION_RE = re.compile(r"[A-Za-z0-9_.+-]+")  # what obsidian_setup.py accepts as a version


def get(url: str) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": "nest-obsidian-lock"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    if len(data) > MAX_BYTES:
        raise SystemExit(f"{url}: larger than {MAX_BYTES} bytes, not locked")
    return data


def entry_for(key: str, repo: str, names: tuple[str, ...], id_field: str) -> dict:
    raw = get(f"https://raw.githubusercontent.com/{repo}/HEAD/manifest.json")
    if raw is None:
        raise SystemExit(f"{repo}: no manifest.json at HEAD")
    manifest = json.loads(raw)
    if manifest.get(id_field) != key:
        raise SystemExit(f"{repo}: manifest {id_field} is {manifest.get(id_field)!r}, expected {key!r}")
    version = manifest.get("version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version) or ".." in version:
        raise SystemExit(f"{repo}: manifest version {version!r} is not one obsidian_setup.py would accept")
    files: dict[str, dict] = {}
    released: dict = {}
    for name in names:
        data = get(f"https://github.com/{repo}/releases/download/{version}/{name}")
        if data is None:
            if name in OPTIONAL:
                continue
            raise SystemExit(f"{repo} {version}: release has no {name}")
        files[name] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        if name == "manifest.json":
            released = json.loads(data)  # the very bytes that were hashed
    if not isinstance(released, dict) or released.get("version") != version or released.get(id_field) != key:
        raise SystemExit(f"{repo} {version}: the released manifest does not match the repository's")
    return {
        "name": str(manifest.get("name", key)),
        "repo": repo,
        "version": version,
        "minAppVersion": str(manifest.get("minAppVersion", "")),
        "files": files,
    }


def build() -> dict:
    return {
        "generated": date.today().isoformat(),
        "plugins": {key: entry_for(key, repo, PLUGIN_FILES, "id") for key, repo in PLUGINS.items()},
        "themes": {key: entry_for(key, repo, THEME_FILES, "name") for key, repo in THEMES.items()},
    }


def differences(old: dict, new: dict) -> list[str]:
    """What a fresh run would change in the lock file, one line each; the date does not count."""
    lines: list[str] = []
    for kind in ("plugins", "themes"):
        was = old.get(kind) if isinstance(old.get(kind), dict) else {}
        now = new[kind]
        label = kind[:-1]
        for key in sorted(set(was) - set(now)):
            lines.append(f"{label} {key}: in the lock file, no longer in this tool's table")
        for key, entry in now.items():
            if key not in was:
                lines.append(f"{label} {key}: none -> {entry['version']}")
                continue
            before = was[key] if isinstance(was[key], dict) else {}
            if before.get("version") != entry["version"]:
                lines.append(f"{label} {key}: {before.get('version', 'none')} -> {entry['version']}")
                continue
            if before.get("repo") != entry["repo"]:
                lines.append(f"{label} {key}: repository {before.get('repo')} -> {entry['repo']}")
            old_files = before.get("files") if isinstance(before.get("files"), dict) else {}
            for name in sorted(set(old_files) | set(entry["files"])):
                a = (old_files.get(name) or {}).get("sha256")
                b = (entry["files"].get(name) or {}).get("sha256")
                if a != b:
                    lines.append(f"{label} {key} {entry['version']}: {name} changed upstream under the same "
                                 f"version ({str(a)[:12]} -> {str(b)[:12]})")
            if before.get("name") != entry["name"]:
                lines.append(f"{label} {key}: name {before.get('name')!r} -> {entry['name']!r}")
            if before.get("minAppVersion", "") != entry["minAppVersion"]:
                lines.append(f"{label} {key}: needs Obsidian {before.get('minAppVersion') or '?'} -> "
                             f"{entry['minAppVersion'] or '?'}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare with upstream, write nothing")
    args = parser.parse_args()
    new = build()
    if args.check:
        old = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.is_file() else {}
        behind = differences(old, new)
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
