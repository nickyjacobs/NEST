# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Put the Obsidian plugins and the theme of a vault in place, so nobody has to click through a list.

Obsidian keeps a community plugin as three files in `<vault>/.obsidian/plugins/<id>/` (`main.js`,
`manifest.json`, optional `styles.css`) next to the plugin's settings in `data.json`, and a theme
as `manifest.json` and `theme.css` in `<vault>/.obsidian/themes/<Name>/`. This script downloads
those files from each project's own GitHub release, at the exact version the lock file names,
and checks every file against the SHA-256 in the lock file before it lands in the vault. The
request goes to github.com over https and GitHub redirects it to its own storage; what guards
the content is the checksum, not the address.

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
Every command takes --json for machine-readable output: always one JSON document, also for an
error. install and restore take --assume-closed, only for when the user has confirmed that
Obsidian is closed and the check below still refuses.

What install does:
  - It installs the plugins listed in the vault's `.obsidian/community-plugins.json` and the theme
    named as `cssTheme` in `.obsidian/appearance.json`, as far as the lock file knows them. A name
    the lock file does not know is reported and left to the user.
  - It never touches `data.json`, `community-plugins.json` or `appearance.json`: those are the
    setup's and the user's.
  - A plugin or theme that is already installed (a `manifest.json` with the right id or name,
    and the code next to it) is left alone, whatever its version: Obsidian updates it from then on.
  - A folder whose `manifest.json` names something else is somebody's own plugin or theme: it is
    refused and nothing in it is touched. A folder without a `manifest.json` can only hold the
    leftovers of an interrupted run, and is filled again.
  - A file whose checksum differs from the lock file stops that plugin; nothing of it is written.
  - `manifest.json` is written last, so an interrupted run never looks like a finished install.
  - A plugin that needs a newer Obsidian than the one found is skipped with that reason.
  - It writes only regular files directly inside `.obsidian/plugins/<id>/` and
    `.obsidian/themes/<name>/`. When `.obsidian`, one of those folders or a file in them is a
    symbolic link or a junction, that item is refused: nothing is written or read through a link.
  - One item that fails does not stop the others; every item gets its own result.

What restore does: for every plugin in the lock file with a `data.json.bak` that differs from
`data.json`, it moves the current `data.json` aside as `data.json.before-restore` (then `-2`,
`-3`: an earlier kept copy is never overwritten) and moves the backup into its place. The backup
is used up by that, so a second restore finds nothing and cannot undo what changed since.

The vault must not be open in Obsidian while install or restore write: Obsidian rewrites its
settings files from memory and would undo the change. The check reads Obsidian's own list of
vaults (`obsidian.json` in its settings folder) and looks for a running Obsidian. A vault that
Obsidian has never opened, or that is closed, is safe even while Obsidian shows another vault.
In doubt it refuses: a list that cannot be read, or an open mark without proof that Obsidian is
not running (on Linux the process list is never that proof), counts as open.

What stays for the user: open the vault and click "Trust author and enable plugins" once. That
choice lives in the app on that device, not in the vault, so no file can make it for them.

Exit status, as in the other scripts of the kit: 0 when everything asked for is in place, 1 when
something was skipped, refused or failed or the environment said no (the output says what and
why), 2 on wrong usage. A plugin the vault lists and the lock file does not know is reported and
left to the user; it does not make install or status fail.

The lock file is `obsidian.lock.json` next to this script; --lock points at another one.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

LOCK_NAME = "obsidian.lock.json"
MAX_BYTES = 40 * 1024 * 1024
TIMEOUT = 30
PLUGIN_FILES = ("main.js", "styles.css", "manifest.json")  # manifest.json last
THEME_FILES = ("theme.css", "manifest.json")
CODE_FILE = {"plugin": "main.js", "theme": "theme.css"}
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
VERSION_RE = re.compile(r"[A-Za-z0-9_.+-]+")
NAME_RE = re.compile(r"[A-Za-z0-9 _.-]+")
SHA_RE = re.compile(r"[0-9a-f]{64}")
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}
ITEM_ERRORS = (OSError, http.client.HTTPException, ValueError)  # one item's trouble, never the whole run's


class SetupError(Exception):
    """A problem the user can act on; printed without a traceback."""


class Refused(SetupError):
    """One plugin or theme this script will not touch, with the reason."""


# --- small helpers ---------------------------------------------------------------------------


def read_json(path: Path, pairs_hook=None):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=pairs_hook)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, RecursionError) as exc:
        raise SetupError(f"cannot read {path}: {str(exc)[:200]}") from exc


def system() -> str:
    """'mac', 'windows' or 'linux' (everything else)."""
    if sys.platform == "darwin":
        return "mac"
    return "windows" if os.name == "nt" else "linux"


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
        # macOS hands out a name composed or decomposed, depending on who asks: compare one form.
        return unicodedata.normalize("NFC", os.path.normcase(str(p)).rstrip("\\/")).casefold()

    return norm(a) == norm(b)


# --- Obsidian on this computer ---------------------------------------------------------------


def config_dirs() -> list[Path]:
    """The folders where Obsidian keeps its own settings, most likely first."""
    override = os.environ.get("NEST_OBSIDIAN_CONFIG")
    if override:
        return [Path(override)]
    home = Path.home()
    found: list[Path] = []
    if system() == "mac":
        found.append(home / "Library" / "Application Support" / "obsidian")
    elif system() == "windows":
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


def vault_registry() -> tuple[list[dict], bool, bool]:
    """Obsidian's own list of vaults: (vaults, found, unclear).

    `found` is False only when no settings folder holds an `obsidian.json`: Obsidian never ran
    here. `unclear` is True when a list exists and cannot be read or is not shaped as expected,
    so a vault may be open without this script seeing it.
    """
    vaults: list[dict] = []
    found = unclear = False
    for folder in config_dirs():
        try:
            data = read_json(folder / "obsidian.json")
        except SetupError:
            found = unclear = True
            continue
        if data is None:
            continue
        found = True
        if not isinstance(data, dict):
            unclear = True
            continue
        entries = data.get("vaults", {})
        if not isinstance(entries, dict):
            unclear = True
            continue
        for entry in entries.values():
            if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                vaults.append({"path": entry["path"], "open": bool(entry.get("open")), "ts": entry.get("ts")})
            else:
                unclear = True
    return vaults, found, unclear


def obsidian_running() -> bool | None:
    """True or False when that is certain, None when it is not.

    On Linux "no process called obsidian" proves nothing: some packages run it as `electron`.
    """
    try:
        if system() == "windows":
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=15, check=False,
            )
            if out.returncode != 0:
                return None
            return "obsidian.exe" in out.stdout.lower()
        mac = system() == "mac"
        if not shutil.which("pgrep"):
            return None
        out = subprocess.run(["pgrep", "-x", "Obsidian" if mac else "obsidian"],
                             capture_output=True, text=True, timeout=15, check=False)
        if out.returncode == 0:
            return True
        if out.returncode == 1 and mac:
            return False
        return None
    except (OSError, subprocess.SubprocessError):
        return None


def vault_is_open(vault: Path) -> bool:
    """Whether Obsidian has this vault open right now, as far as can be told. Errs on yes."""
    vaults, found, unclear = vault_registry()
    if not found:
        return False  # no obsidian.json anywhere: Obsidian has never run here
    marked = any(v["open"] for v in vaults if same_path(Path(v["path"]), vault))
    if not marked and not unclear:
        return False
    return obsidian_running() is not False  # only a clear "not running" clears a mark or a doubt


def installer_version() -> tuple[int, ...]:
    """The version of the installed app itself, where it can be read (macOS)."""
    best: tuple[int, ...] = ()
    if system() == "mac":
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


def folder_name_problem(key: str) -> str | None:
    """Why `key` cannot be the name of one folder on every system, or None when it can."""
    if not NAME_RE.fullmatch(key):
        return "has characters outside letters, digits, space, dot, dash and underscore"
    if key[0] in ". " or key[-1] in ". ":
        return "starts or ends with a dot or a space"
    if key.split(".")[0].upper() in RESERVED:
        return "is a reserved device name on Windows"
    return None


def no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    seen: dict = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"the key {key!r} is there twice")
        seen[key] = value
    return seen


def load_lock(path: Path) -> dict:
    data = read_json(path, pairs_hook=no_duplicate_keys)
    if not isinstance(data, dict):
        raise SetupError(f"{path} is not a lock file")
    lock = {"plugins": {}, "themes": {}}
    for kind, allowed in (("plugins", PLUGIN_FILES), ("themes", THEME_FILES)):
        entries = data.get(kind)
        if not isinstance(entries, dict):
            raise SetupError(f"{path}: '{kind}' is missing or not an object")
        code = CODE_FILE[kind[:-1]]
        folded: dict[str, str] = {}
        for key, entry in entries.items():
            where = f"{path}: {kind}.{key!r}"
            problem = folder_name_problem(key)
            if problem:
                raise SetupError(f"{where}: the name {problem}")
            if folded.setdefault(key.casefold(), key) != key:
                raise SetupError(f"{where}: the same folder as {folded[key.casefold()]!r} where case does not count")
            if not isinstance(entry, dict):
                raise SetupError(f"{where}: not a valid entry")
            repo, version, files = entry.get("repo"), entry.get("version"), entry.get("files")
            if not isinstance(repo, str) or not REPO_RE.fullmatch(repo) or set(repo.split("/")) & {".", ".."}:
                raise SetupError(f"{where}: 'repo' must look like owner/name")
            if not isinstance(version, str) or not VERSION_RE.fullmatch(version) or ".." in version:
                raise SetupError(f"{where}: 'version' is missing or has odd characters")
            name, min_app = entry.get("name", key), entry.get("minAppVersion", "")
            if not isinstance(name, str) or not isinstance(min_app, str):
                raise SetupError(f"{where}: 'name' and 'minAppVersion' must be text")
            if not isinstance(files, dict) or "manifest.json" not in files or code not in files:
                raise SetupError(f"{where}: 'files' must name manifest.json and {code}")
            for file_name, meta in files.items():
                if file_name not in allowed:
                    raise SetupError(f"{where}: unexpected file {file_name!r}")
                digest = meta.get("sha256") if isinstance(meta, dict) else None
                if not isinstance(digest, str) or not SHA_RE.fullmatch(digest):
                    raise SetupError(f"{where}: {file_name} has no sha256")
            lock[kind][key] = {
                "name": name,
                "repo": repo,
                "version": version,
                "minAppVersion": min_app,
                "files": {file_name: files[file_name]["sha256"] for file_name in allowed if file_name in files},
            }
    return lock


def asset_url(repo: str, version: str, name: str) -> str:
    return f"https://github.com/{repo}/releases/download/{version}/{name}"


def fetch(url: str) -> bytes:
    """Download one release file. Tests replace this function.

    The request goes to github.com over https; GitHub answers a release download with a redirect
    to its own storage, which is followed. The caller checks the bytes against the lock file.
    """
    if not url.startswith("https://github.com/"):
        raise SetupError(f"refusing to download from {url}")
    last: Exception | None = None
    for _ in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "nest-obsidian-setup"})
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - https only, checked above
                data = response.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise SetupError(f"download failed ({exc.code}): {url}") from exc
        except (http.client.InvalidURL, ValueError) as exc:
            raise SetupError(f"download failed, not a usable address: {url!r} ({exc})") from exc
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as exc:
            last = exc
            continue
        if len(data) > MAX_BYTES:
            raise SetupError(f"{url} is larger than expected")
        return data
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


def is_link(path: Path) -> bool:
    """A symbolic link or, on Windows, a junction."""
    return path.is_symlink() or bool(getattr(os.path, "isjunction", lambda _: False)(path))


def item_folder(vault: Path, kind: str, key: str) -> Path:
    """The folder of one plugin or theme, after checking that no link leads there."""
    problem = folder_name_problem(key)
    if problem:
        raise Refused(f"the name {problem}")
    config = vault / ".obsidian"
    parent = config / ("plugins" if kind == "plugin" else "themes")
    folder = parent / key
    for path in (config, parent, folder):
        shown = path.relative_to(vault).as_posix()
        if is_link(path):
            raise Refused(f"{shown} is a link to another place; this script only writes inside the vault itself")
        if os.path.lexists(path) and not path.is_dir():
            raise Refused(f"{shown} is not a folder")
    try:
        inside = folder.resolve().is_relative_to(vault.resolve())
    except OSError as exc:
        raise Refused(f"cannot tell where {folder.relative_to(vault).as_posix()} really is: {exc}") from exc
    if not inside:
        raise Refused(f"{folder.relative_to(vault).as_posix()} is not inside the vault")
    return folder


def check_files(folder: Path, names) -> None:
    """Every name is absent or a regular file, never a link: safe to read and to replace."""
    for name in names:
        path = folder / name
        if is_link(path):
            raise Refused(f"{name} in {folder.name} is a link; nothing is written or read through a link")
        if os.path.lexists(path) and not path.is_file():
            raise Refused(f"{name} in {folder.name} is not a regular file")


def folder_state(folder: Path, kind: str, key: str) -> tuple[str, str | None]:
    """('installed', version), ('free', None) or ('foreign', why it is not ours to touch)."""
    manifest_path = folder / "manifest.json"
    if not os.path.lexists(manifest_path):
        return "free", None  # nothing, or the leftovers of an interrupted run
    try:
        manifest = read_json(manifest_path)
    except SetupError:
        return "foreign", "its manifest.json cannot be read, so it is not clear whose folder this is"
    field = "id" if kind == "plugin" else "name"
    if not isinstance(manifest, dict) or manifest.get(field) != key:
        other = manifest.get(field) if isinstance(manifest, dict) else None
        return "foreign", f"the folder holds another {kind} ({other!r}); it is left as it is"
    if not (folder / CODE_FILE[kind]).is_file():
        return "free", None  # a manifest without the code: incomplete, install again
    return "installed", str(manifest.get("version", "?"))


def settings_set_aside(folder: Path) -> bool:
    """A `data.json.bak` that holds something else than `data.json` (or there is no `data.json`)."""
    backup, current = folder / "data.json.bak", folder / "data.json"
    if not os.path.lexists(backup):
        return False
    try:
        return not (current.is_file() and current.read_bytes() == backup.read_bytes())
    except OSError:
        return True


def item_state(vault: Path, kind: str, key: str) -> dict:
    state: dict = {"kind": kind, "id": key, "installed": None, "blocked": None}
    if kind == "plugin":
        state.update(settings=False, set_aside=False)
    try:
        folder = item_folder(vault, kind, key)
        check_files(folder, PLUGIN_FILES if kind == "plugin" else THEME_FILES)
        found, detail = folder_state(folder, kind, key)
        if kind == "plugin":
            state.update(settings=(folder / "data.json").is_file(), set_aside=settings_set_aside(folder))
    except Refused as exc:
        state["blocked"] = str(exc)
        return state
    except ITEM_ERRORS as exc:
        state["blocked"] = f"cannot look into the folder: {exc}"
        return state
    if found == "installed":
        state["installed"] = detail
    elif found == "foreign":
        state["blocked"] = detail
    return state


def write_file(folder: Path, name: str, data: bytes) -> None:
    """Write through a fresh temporary file in the same folder, then move it into place."""
    check_files(folder, [name])
    handle, temp = tempfile.mkstemp(dir=folder, prefix=".nest-", suffix=".part")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        os.chmod(temp, 0o644)
        os.replace(temp, folder / name)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def install_item(vault: Path, kind: str, key: str, entry: dict, app: str | None, dry_run: bool) -> dict:
    result = {"kind": kind, "id": key, "name": entry["name"], "version": entry["version"]}
    order = PLUGIN_FILES if kind == "plugin" else THEME_FILES
    folder = item_folder(vault, kind, key)
    check_files(folder, order)
    found, detail = folder_state(folder, kind, key)
    if found == "installed":
        return {**result, "status": "present", "installed": detail}
    if found == "foreign":
        raise Refused(detail)
    need = entry["minAppVersion"]
    if need and app and version_tuple(app) < version_tuple(need):
        return {**result, "status": "skipped",
                "reason": f"needs Obsidian {need} or newer, found {app}: update Obsidian and run this again. "
                          "If Obsidian is already newer than that, open Obsidian once so it finishes updating, "
                          "quit it, and run this again"}
    if dry_run:
        return {**result, "status": "would-install"}
    blobs: dict[str, bytes] = {}
    for name in order:
        if name not in entry["files"]:
            continue
        data = fetch(asset_url(entry["repo"], entry["version"], name))
        if hashlib.sha256(data).hexdigest() != entry["files"][name]:
            return {**result, "status": "failed",
                    "reason": f"{name} does not match the checksum in the lock file; nothing was written"}
        blobs[name] = data
    folder.mkdir(parents=True, exist_ok=True)
    folder = item_folder(vault, kind, key)  # again: the downloads took a while
    if folder_state(folder, kind, key)[0] == "foreign":
        raise Refused("the folder changed while the files were downloaded; nothing was written")
    for name in order:  # manifest.json is last in both orders
        if name in blobs:
            write_file(folder, name, blobs[name])
    return {**result, "status": "installed"}


def install_safely(vault: Path, kind: str, key: str, entry: dict, app: str | None, dry_run: bool) -> dict:
    """install_item, with every refusal and every error turned into this item's result."""
    result = {"kind": kind, "id": key, "name": entry["name"], "version": entry["version"]}
    try:
        return install_item(vault, kind, key, entry, app, dry_run)
    except Refused as exc:
        return {**result, "status": "refused", "reason": str(exc)}
    except (SetupError, *ITEM_ERRORS) as exc:
        return {**result, "status": "failed", "reason": str(exc) or type(exc).__name__}


def restore_item(vault: Path, key: str) -> dict | None:
    """Move one plugin's `data.json.bak` back into place; None when there is nothing to do."""
    plain = vault / ".obsidian" / "plugins" / key
    if not os.path.lexists(plain / "data.json.bak"):
        return None
    folder = item_folder(vault, "plugin", key)
    backup, current = folder / "data.json.bak", folder / "data.json"
    check_files(folder, ["data.json.bak", "data.json"])
    kept: Path | None = None
    if current.is_file():
        if current.read_bytes() == backup.read_bytes():
            return {"id": key, "status": "same"}
        number = 1
        while True:
            kept = folder / ("data.json.before-restore" + (f"-{number}" if number > 1 else ""))
            if not os.path.lexists(kept):
                break
            number += 1
        os.replace(current, kept)
    try:
        os.replace(backup, current)
    except OSError:
        if kept is not None:
            os.replace(kept, current)  # put the user's file back where it was
        raise
    return {"id": key, "status": "restored", "kept": kept.name if kept else None}


def require_closed(vault: Path, assume_closed: bool) -> None:
    if assume_closed:
        return
    if vault_is_open(vault):
        raise SetupError(
            "this vault is open in Obsidian, or it cannot be ruled out that it is. Quit Obsidian completely "
            "(the app, not only the window) and run this again. --assume-closed is only for when the user "
            "has confirmed that Obsidian is closed and this check still refuses."
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
    for key in dict.fromkeys(plugins):
        if only is not None and key not in only:
            continue
        if key in lock["plugins"]:
            results.append(install_safely(vault, "plugin", key, lock["plugins"][key], app, args.dry_run))
        else:
            unknown.append(key)
    if theme and (only is None or theme in only):
        if theme in lock["themes"]:
            results.append(install_safely(vault, "theme", theme, lock["themes"][theme], app, args.dry_run))
        else:
            unknown.append(theme)
    not_asked = sorted(only - set(plugins) - {theme}) if only is not None else []
    set_aside = [r["id"] for r in results if r["kind"] == "plugin" and item_state(vault, "plugin", r["id"])["set_aside"]]
    report = {"vault": str(vault), "obsidian": app, "results": results, "unknown": unknown,
              "not_asked": not_asked, "set_aside": set_aside, "listed": bool(plugins or theme)}
    bad = any(r["status"] in ("failed", "skipped", "refused") for r in results)
    # A name the user typed after --only must lead somewhere; a plugin the vault merely lists may be unknown.
    bad = bad or bool(not_asked) or (only is not None and bool(unknown))
    return report, 1 if bad else 0


def cmd_status(args) -> tuple[dict, int]:
    vault = Path(args.vault)
    lock = load_lock(find_lock(args.lock))
    plugins, theme = wanted(vault)
    items = []
    for key in dict.fromkeys(plugins):
        state = item_state(vault, "plugin", key)
        state["known"] = key in lock["plugins"]
        items.append(state)
    if theme:
        state = item_state(vault, "theme", theme)
        state["known"] = theme in lock["themes"]
        items.append(state)
    report = {"vault": str(vault), "obsidian": app_version(), "open": vault_is_open(vault), "items": items}
    missing = any(i["installed"] is None and i["known"] for i in items)  # an unknown one is the user's own
    return report, 1 if missing else 0


def cmd_restore(args) -> tuple[dict, int]:
    vault = Path(args.vault)
    lock = load_lock(find_lock(args.lock))
    require_closed(vault, args.assume_closed)
    obsidian_dir(vault)
    results: list[dict] = []
    for key in sorted(lock["plugins"]):
        try:
            result = restore_item(vault, key)
        except (SetupError, *ITEM_ERRORS) as exc:
            result = {"id": key, "status": "failed", "reason": str(exc) or type(exc).__name__}
        if result:
            results.append(result)
    report = {
        "vault": str(vault), "results": results,
        "restored": [r["id"] for r in results if r["status"] == "restored"],
        "already_same": [r["id"] for r in results if r["status"] == "same"],
    }
    return report, 1 if any(r["status"] == "failed" for r in results) else 0


def cmd_vaults(args) -> tuple[dict, int]:
    vaults, found, _ = vault_registry()
    out = []
    for entry in vaults:
        path = Path(entry["path"])
        exists = path.is_dir()
        notes = 0
        if exists:
            try:
                for index, _note in enumerate(path.rglob("*.md"), start=1):
                    notes = index
                    if index >= 5000:
                        break
            except OSError:
                pass
        out.append({"path": entry["path"], "exists": exists, "open": entry["open"], "notes": notes})
    return {"obsidian_found": found, "vaults": out}, 0


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
        for key in report["not_asked"]:
            print(f"  --only names {key}, but the vault does not ask for it: nothing done for it")
        if report["set_aside"]:
            print("  settings set aside by Obsidian (data.json.bak) found for: " + ", ".join(report["set_aside"]))
            print("  run `restore` to put them back.")
        if not report["listed"]:
            print("  nothing to install: the vault lists no community plugins and no theme.")
    elif command == "status":
        print(f"Vault: {report['vault']}  (Obsidian {report['obsidian'] or 'version not found'}, "
              f"{'open' if report['open'] else 'closed'})")
        for i in report["items"]:
            bits = [f"installed {i['installed']}" if i["installed"] else "NOT installed"]
            if i["kind"] == "plugin":
                bits.append("settings" if i["settings"] else "no settings file")
                if i["set_aside"]:
                    bits.append("other settings set aside in data.json.bak")
            if not i["known"]:
                bits.append("not in the lock file")
            if i["blocked"]:
                bits.append(i["blocked"])
            print(f"  {i['kind']:<6} {i['id']}: " + ", ".join(bits))
    elif command == "restore":
        for r in report["results"]:
            if r["status"] == "restored":
                kept = f"; the file that was there is kept as {r['kept']}" if r["kept"] else ""
                print(f"  settings put back for {r['id']}{kept}")
            elif r["status"] == "failed":
                print(f"  failed for {r['id']}: {r['reason']}")
        if not report["restored"] and not any(r["status"] == "failed" for r in report["results"]):
            print("Nothing to restore.")
    elif command == "vaults":
        if not report["obsidian_found"]:
            print("Obsidian has no settings on this computer (not installed, or never opened).")
        for v in report["vaults"]:
            state = "missing" if not v["exists"] else f"{v['notes']}{'+' if v['notes'] >= 5000 else ''} notes"
            print(f"  {v['path']}  ({state}{', open' if v['open'] else ''})")


class Parser(argparse.ArgumentParser):
    """argparse, with a usage error also as JSON on stdout when --json was given."""

    json_errors = False

    def error(self, message: str):
        if Parser.json_errors:
            print(json.dumps({"error": f"usage: {message}"}, ensure_ascii=False))
        super().error(message)  # usage on stderr, exit status 2


def build_parser() -> argparse.ArgumentParser:
    parser = Parser(description="Install the Obsidian plugins and theme a vault asks for.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("install", "status", "restore", "vaults"):
        p = sub.add_parser(name)
        p.add_argument("--json", action="store_true", help="machine-readable output")
        if name != "vaults":
            p.add_argument("--vault", required=True, help="the vault folder (the wiki)")
            p.add_argument("--lock", help=f"another lock file than {LOCK_NAME} next to this script")
        if name in ("install", "restore"):
            p.add_argument("--assume-closed", action="store_true",
                           help="skip the check that the vault is closed; only after the user confirmed it is")
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
    argv = sys.argv[1:] if argv is None else argv
    Parser.json_errors = "--json" in argv
    args = build_parser().parse_args(argv)
    try:
        report, code = COMMANDS[args.command](args)
    except (SetupError, OSError) as exc:
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
