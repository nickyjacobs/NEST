# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Put the Obsidian plugins and the theme of a vault in place, so nobody has to click through a list.

Obsidian keeps a community plugin as three files in `<vault>/.obsidian/plugins/<id>/` (`main.js`,
`manifest.json`, optional `styles.css`) next to the plugin's settings in `data.json`, and a theme
as `manifest.json` and `theme.css` in `<vault>/.obsidian/themes/<Name>/`. This script downloads
those files from each project's own GitHub release, at the exact version the lock file names,
and checks every file against the SHA-256 in the lock file before it lands in the vault.

Why a script and not the in-app browser: when a plugin is installed from inside Obsidian and its
folder holds a `data.json` but no `manifest.json` yet, Obsidian renames that settings file to
`data.json.bak`. A setup that writes the settings first and lets the user install afterwards
loses its settings every time. With the plugin files in place beforehand, the settings stay.

Usage:
  obsidian_setup.py install --vault <wiki>   download what the vault asks for and is not there yet
       --only <id,id>                        only these plugin ids or theme names
       --dry-run                             say what would happen, write nothing
  obsidian_setup.py status --vault <wiki>    what is listed, installed, missing or set aside
  obsidian_setup.py restore --vault <wiki>   put a `data.json.bak` that Obsidian set aside back
  obsidian_setup.py vaults                   the vaults Obsidian knows on this computer
Every command takes --json for machine-readable output. install and restore take
--assume-closed when the check below is wrong.

What install does:
  - It installs the plugins listed in the vault's `.obsidian/community-plugins.json` and the theme
    named as `cssTheme` in `.obsidian/appearance.json`, as far as the lock file knows them. A name
    the lock file does not know is reported and left to the user.
  - It never touches `data.json`, `community-plugins.json` or `appearance.json`: those are the
    setup's and the user's.
  - A plugin or theme that is already installed (a `manifest.json` with the right id or name) is
    left alone, whatever its version: Obsidian updates it from then on.
  - A file whose checksum differs from the lock file stops that plugin; nothing of it is written.
  - `manifest.json` is written last, so an interrupted run never looks like a finished install.
  - A plugin that needs a newer Obsidian than the one found is skipped with that reason.

The vault must not be open in Obsidian while install or restore write: Obsidian rewrites its
settings files from memory and would undo the change. The check reads Obsidian's own list of
vaults (`obsidian.json` in its settings folder) and looks for a running Obsidian. A vault that
Obsidian has never opened, or that is closed, is safe even while Obsidian shows another vault.

What stays for the user: open the vault and click "Trust author and enable plugins" once. That
choice lives in the app on that device, not in the vault, so no file can make it for them.

Exit status: 0 when everything asked for is in place, 1 on a usage or environment error, 2 when
something was skipped or failed (the output says what and why).

The lock file is `obsidian.lock.json` next to this script; --lock points at another one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

LOCK_NAME = "obsidian.lock.json"
MAX_BYTES = 40 * 1024 * 1024
TIMEOUT = 30
PLUGIN_FILES = ("main.js", "styles.css", "manifest.json")  # manifest.json last
THEME_FILES = ("theme.css", "manifest.json")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
VERSION_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")
NAME_RE = re.compile(r"^[A-Za-z0-9 _.-]+$")


class SetupError(Exception):
    """A problem the user can act on; printed without a traceback."""


# --- small helpers ---------------------------------------------------------------------------


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise SetupError(f"cannot read {path}: {exc}") from exc


def version_tuple(text: str) -> tuple[int, ...]:
    """'1.14.0' -> (1, 14, 0). Anything after the first non-numeric part is ignored."""
    parts: list[int] = []
    for piece in str(text).split("."):
        digits = re.match(r"\d+", piece)
        if not digits:
            break
        parts.append(int(digits.group()))
    return tuple(parts)


def same_path(a: Path, b: Path) -> bool:
    def norm(p: Path) -> str:
        try:
            p = p.resolve()
        except OSError:
            p = p.absolute()
        return os.path.normcase(str(p)).rstrip("\\/").casefold()

    return norm(a) == norm(b)


# --- Obsidian on this computer ---------------------------------------------------------------


def config_dirs() -> list[Path]:
    """The folders where Obsidian keeps its own settings, most likely first."""
    override = os.environ.get("NEST_OBSIDIAN_CONFIG")
    if override:
        return [Path(override)]
    home = Path.home()
    found: list[Path] = []
    if sys.platform == "darwin":
        found.append(home / "Library" / "Application Support" / "obsidian")
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            found.append(Path(appdata) / "obsidian")
        found.append(home / "AppData" / "Roaming" / "obsidian")
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            found.append(Path(xdg) / "obsidian")
        found.append(home / ".config" / "obsidian")
        found.append(home / ".var" / "app" / "md.obsidian.Obsidian" / "config" / "obsidian")
        found.append(home / "snap" / "obsidian" / "current" / ".config" / "obsidian")
    unique: list[Path] = []
    for path in found:
        if path not in unique:
            unique.append(path)
    return unique


def known_vaults() -> list[dict] | None:
    """Obsidian's own list of vaults, or None when Obsidian has no settings here."""
    seen_any = False
    vaults: list[dict] = []
    for folder in config_dirs():
        try:
            data = read_json(folder / "obsidian.json")
        except SetupError:
            continue
        if not isinstance(data, dict):
            continue
        seen_any = True
        entries = data.get("vaults")
        if not isinstance(entries, dict):
            continue
        for entry in entries.values():
            if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                vaults.append({"path": entry["path"], "open": bool(entry.get("open")), "ts": entry.get("ts")})
    return vaults if seen_any else None


def obsidian_running() -> bool | None:
    """True or False when the process list could be read, None when it could not."""
    try:
        if os.name == "nt":
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=15, check=False,
            )
            if out.returncode != 0:
                return None
            return "obsidian.exe" in out.stdout.lower()
        name = "Obsidian" if sys.platform == "darwin" else "obsidian"
        if not shutil.which("pgrep"):
            return None
        out = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True, timeout=15, check=False)
        if out.returncode in (0, 1):
            return out.returncode == 0
        return None
    except (OSError, subprocess.SubprocessError):
        return None


def vault_is_open(vault: Path) -> bool:
    """Whether Obsidian has this vault open right now, as far as can be told. Errs on yes."""
    vaults = known_vaults()
    if vaults is None:
        return False  # Obsidian has never run here
    listed = [v for v in vaults if same_path(Path(v["path"]), vault)]
    if not any(v["open"] for v in listed):
        return False
    return obsidian_running() is not False  # marked open: only a clear "not running" clears it


def installer_version() -> tuple[int, ...]:
    """The version of the installed app itself, where it can be read (macOS)."""
    best: tuple[int, ...] = ()
    if sys.platform == "darwin":
        for app in (Path("/Applications/Obsidian.app"), Path.home() / "Applications" / "Obsidian.app"):
            try:
                with (app / "Contents" / "Info.plist").open("rb") as handle:
                    candidate = version_tuple(plistlib.load(handle).get("CFBundleShortVersionString", ""))
            except (OSError, ValueError, plistlib.InvalidFileException):
                continue
            best = max(best, candidate)
    return best


def app_version() -> str | None:
    """The Obsidian version on this computer, or None when it cannot be found.

    Obsidian updates itself by dropping `obsidian-<version>.asar` in its settings folder, so the
    newest of those counts; the installed app is the fallback.
    """
    best = installer_version()
    for folder in config_dirs():
        try:
            names = [p.name for p in folder.glob("obsidian-*.asar")]
        except OSError:
            continue
        for name in names:
            best = max(best, version_tuple(name[len("obsidian-"):-len(".asar")]))
    return ".".join(str(n) for n in best) if best else None


# --- the lock file ---------------------------------------------------------------------------


def find_lock(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise SetupError(f"lock file not found: {path}")
        return path
    here = Path(__file__).resolve().parent
    path = here / LOCK_NAME
    if path.is_file():
        return path
    raise SetupError(f"{LOCK_NAME} not found next to {Path(__file__).name}; pass --lock <file>")


def load_lock(path: Path) -> dict:
    data = read_json(path)
    if not isinstance(data, dict):
        raise SetupError(f"{path} is not a lock file")
    lock = {"plugins": {}, "themes": {}}
    for kind, allowed in (("plugins", PLUGIN_FILES), ("themes", THEME_FILES)):
        entries = data.get(kind, {})
        if not isinstance(entries, dict):
            raise SetupError(f"{path}: '{kind}' must be an object")
        for key, entry in entries.items():
            where = f"{path}: {kind}.{key}"
            if not isinstance(entry, dict) or not NAME_RE.match(key) or key in (".", ".."):
                raise SetupError(f"{where}: not a valid entry")
            repo, version, files = entry.get("repo"), entry.get("version"), entry.get("files")
            if not isinstance(repo, str) or not REPO_RE.match(repo):
                raise SetupError(f"{where}: 'repo' must look like owner/name")
            if not isinstance(version, str) or not VERSION_RE.match(version):
                raise SetupError(f"{where}: 'version' is missing or has odd characters")
            if not isinstance(files, dict) or "manifest.json" not in files:
                raise SetupError(f"{where}: 'files' must name manifest.json")
            for name, meta in files.items():
                if name not in allowed:
                    raise SetupError(f"{where}: unexpected file {name!r}")
                digest = meta.get("sha256") if isinstance(meta, dict) else None
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise SetupError(f"{where}: {name} has no sha256")
            lock[kind][key] = {
                "name": entry.get("name", key),
                "repo": repo,
                "version": version,
                "minAppVersion": entry.get("minAppVersion") or "",
                "files": {name: files[name]["sha256"] for name in allowed if name in files},
            }
    return lock


def asset_url(repo: str, version: str, name: str) -> str:
    return f"https://github.com/{repo}/releases/download/{version}/{name}"


def fetch(url: str) -> bytes:
    """Download one release file. Tests replace this function."""
    if not url.startswith("https://github.com/"):
        raise SetupError(f"refusing to download from {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "nest-obsidian-setup"})
    last: Exception | None = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - https only, checked above
                data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise SetupError(f"{url} is larger than expected")
            return data
        except urllib.error.HTTPError as exc:
            raise SetupError(f"download failed ({exc.code}): {url}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
    raise SetupError(f"download failed, is there a connection? {url} ({last})")


# --- the vault -------------------------------------------------------------------------------


def obsidian_dir(vault: Path) -> Path:
    if not vault.is_dir():
        raise SetupError(f"vault folder not found: {vault}")
    return vault / ".obsidian"


def wanted(vault: Path) -> tuple[list[str], str]:
    """The plugin ids and the theme name the vault's own settings ask for."""
    config = obsidian_dir(vault)
    ids = read_json(config / "community-plugins.json")
    plugins = [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []
    appearance = read_json(config / "appearance.json")
    theme = appearance.get("cssTheme", "") if isinstance(appearance, dict) else ""
    return plugins, theme if isinstance(theme, str) else ""


def installed_version(folder: Path, key: str, field: str) -> str | None:
    """The version in the folder's manifest when it belongs to `key`, else None."""
    try:
        manifest = read_json(folder / "manifest.json")
    except SetupError:
        return None
    if isinstance(manifest, dict) and manifest.get(field) == key:
        return str(manifest.get("version", "?"))
    return None


def item_state(vault: Path, kind: str, key: str) -> dict:
    config = obsidian_dir(vault)
    if kind == "plugin":
        folder = config / "plugins" / key
        version = installed_version(folder, key, "id")
        return {
            "kind": kind, "id": key, "installed": version,
            "settings": (folder / "data.json").is_file(),
            "set_aside": (folder / "data.json.bak").is_file(),
        }
    folder = config / "themes" / key
    version = installed_version(folder, key, "name")
    if version is not None and not (folder / "theme.css").is_file():
        version = None
    return {"kind": kind, "id": key, "installed": version}


def install_item(vault: Path, kind: str, key: str, entry: dict, app: str | None, dry_run: bool) -> dict:
    state = item_state(vault, kind, key)
    result = {"kind": kind, "id": key, "name": entry["name"], "version": entry["version"]}
    if state["installed"] is not None:
        return {**result, "status": "present", "installed": state["installed"]}
    need = entry["minAppVersion"]
    if need and app and version_tuple(app) < version_tuple(need):
        return {**result, "status": "skipped",
                "reason": f"needs Obsidian {need} or newer, found {app}: update Obsidian and run this again"}
    if dry_run:
        return {**result, "status": "would-install"}
    order = PLUGIN_FILES if kind == "plugin" else THEME_FILES
    blobs: dict[str, bytes] = {}
    for name in order:
        if name not in entry["files"]:
            continue
        try:
            data = fetch(asset_url(entry["repo"], entry["version"], name))
        except SetupError as exc:
            return {**result, "status": "failed", "reason": str(exc)}
        if hashlib.sha256(data).hexdigest() != entry["files"][name]:
            return {**result, "status": "failed",
                    "reason": f"{name} does not match the checksum in the lock file; nothing was written"}
        blobs[name] = data
    folder = obsidian_dir(vault) / ("plugins" if kind == "plugin" else "themes") / key
    folder.mkdir(parents=True, exist_ok=True)
    for name in order:  # manifest.json is last in both orders
        if name not in blobs:
            continue
        part = folder / (name + ".nest-part")
        part.write_bytes(blobs[name])
        os.replace(part, folder / name)
    return {**result, "status": "installed"}


def require_closed(vault: Path, assume_closed: bool) -> None:
    if assume_closed:
        return
    if vault_is_open(vault):
        raise SetupError(
            "this vault is open in Obsidian. Close Obsidian completely (quit the app, not only the "
            "window) and run this again. If it is closed, add --assume-closed."
        )


# --- commands --------------------------------------------------------------------------------


def cmd_install(args) -> tuple[dict, int]:
    vault = Path(args.vault)
    lock = load_lock(find_lock(args.lock))
    plugins, theme = wanted(vault)
    only = {x.strip() for x in args.only.split(",") if x.strip()} if args.only else None
    if not args.dry_run:
        require_closed(vault, args.assume_closed)
    app = app_version()
    results: list[dict] = []
    unknown: list[str] = []
    for key in plugins:
        if only is not None and key not in only:
            continue
        if key in lock["plugins"]:
            results.append(install_item(vault, "plugin", key, lock["plugins"][key], app, args.dry_run))
        else:
            unknown.append(key)
    if theme and (only is None or theme in only):
        if theme in lock["themes"]:
            results.append(install_item(vault, "theme", theme, lock["themes"][theme], app, args.dry_run))
        else:
            unknown.append(theme)
    set_aside = [r["id"] for r in results if r["kind"] == "plugin" and item_state(vault, "plugin", r["id"])["set_aside"]]
    report = {"vault": str(vault), "obsidian": app, "results": results, "unknown": unknown, "set_aside": set_aside}
    bad = any(r["status"] in ("failed", "skipped") for r in results)
    return report, 2 if bad else 0


def cmd_status(args) -> tuple[dict, int]:
    vault = Path(args.vault)
    lock = load_lock(find_lock(args.lock))
    plugins, theme = wanted(vault)
    items = []
    for key in plugins:
        state = item_state(vault, "plugin", key)
        state["known"] = key in lock["plugins"]
        items.append(state)
    if theme:
        state = item_state(vault, "theme", theme)
        state["known"] = theme in lock["themes"]
        items.append(state)
    report = {"vault": str(vault), "obsidian": app_version(), "open": vault_is_open(vault), "items": items}
    missing = any(i["installed"] is None for i in items)
    return report, 2 if missing else 0


def cmd_restore(args) -> tuple[dict, int]:
    vault = Path(args.vault)
    lock = load_lock(find_lock(args.lock))
    require_closed(vault, args.assume_closed)
    root = obsidian_dir(vault) / "plugins"
    restored: list[str] = []
    same: list[str] = []
    for key in sorted(lock["plugins"]):
        backup = root / key / "data.json.bak"
        current = root / key / "data.json"
        if not backup.is_file():
            continue
        wanted_bytes = backup.read_bytes()
        if current.is_file():
            if current.read_bytes() == wanted_bytes:
                same.append(key)
                continue
            os.replace(current, root / key / "data.json.before-restore")
        part = root / key / "data.json.nest-part"
        part.write_bytes(wanted_bytes)
        os.replace(part, current)
        restored.append(key)
    return {"vault": str(vault), "restored": restored, "already_same": same}, 0


def cmd_vaults(args) -> tuple[dict, int]:
    vaults = known_vaults()
    out = []
    for entry in vaults or []:
        path = Path(entry["path"])
        exists = path.is_dir()
        notes = 0
        if exists:
            try:
                for index, _ in enumerate(path.rglob("*.md"), start=1):
                    notes = index
                    if index >= 5000:
                        break
            except OSError:
                pass
        out.append({"path": entry["path"], "exists": exists, "open": entry["open"], "notes": notes})
    return {"obsidian_found": vaults is not None, "vaults": out}, 0


# --- output ----------------------------------------------------------------------------------


def print_report(command: str, report: dict) -> None:
    if command == "install":
        found = report["obsidian"] or "version not found"
        print(f"Vault: {report['vault']}  (Obsidian {found})")
        for r in report["results"]:
            label = f"{r['kind']} {r['name']} {r['version']}"
            if r["status"] == "present":
                print(f"  already there   {label} (installed: {r['installed']})")
            elif r["status"] in ("installed", "would-install"):
                print(f"  {r['status']:<15} {label}")
            else:
                print(f"  {r['status']:<15} {label}: {r['reason']}")
        for key in report["unknown"]:
            print(f"  not in the lock file, left to you: {key}")
        if report["set_aside"]:
            print("  settings set aside by Obsidian (data.json.bak) found for: " + ", ".join(report["set_aside"]))
            print("  run `restore` to put them back.")
        if not report["results"] and not report["unknown"]:
            print("  nothing to install: the vault lists no community plugins and no theme.")
    elif command == "status":
        print(f"Vault: {report['vault']}  (Obsidian {report['obsidian'] or 'version not found'}, "
              f"{'open' if report['open'] else 'closed'})")
        for i in report["items"]:
            bits = [f"installed {i['installed']}" if i["installed"] else "NOT installed"]
            if i["kind"] == "plugin":
                bits.append("settings" if i["settings"] else "no settings file")
                if i["set_aside"]:
                    bits.append("data.json.bak present")
            if not i["known"]:
                bits.append("not in the lock file")
            print(f"  {i['kind']:<6} {i['id']}: " + ", ".join(bits))
    elif command == "restore":
        if report["restored"]:
            print("Settings put back for: " + ", ".join(report["restored"]))
            print("The file that was there is kept as data.json.before-restore.")
        else:
            print("Nothing to restore.")
    elif command == "vaults":
        if not report["obsidian_found"]:
            print("Obsidian has no settings on this computer (not installed, or never opened).")
        for v in report["vaults"]:
            state = "missing" if not v["exists"] else f"{v['notes']}{'+' if v['notes'] >= 5000 else ''} notes"
            print(f"  {v['path']}  ({state}{', open' if v['open'] else ''})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install the Obsidian plugins and theme a vault asks for.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("install", "status", "restore", "vaults"):
        p = sub.add_parser(name)
        p.add_argument("--json", action="store_true", help="machine-readable output")
        if name != "vaults":
            p.add_argument("--vault", required=True, help="the vault folder (the wiki)")
            p.add_argument("--lock", help=f"another lock file than {LOCK_NAME} next to this script")
        if name in ("install", "restore"):
            p.add_argument("--assume-closed", action="store_true", help="skip the check that the vault is closed")
        if name == "install":
            p.add_argument("--only", help="comma-separated plugin ids or theme names")
            p.add_argument("--dry-run", action="store_true", help="write nothing")
    return parser


COMMANDS = {"install": cmd_install, "status": cmd_status, "restore": cmd_restore, "vaults": cmd_vaults}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        report, code = COMMANDS[args.command](args)
    except SetupError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"obsidian_setup: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(args.command, report)
    return code


if __name__ == "__main__":
    sys.exit(main())
