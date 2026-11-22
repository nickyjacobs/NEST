"""Tests for obsidian_setup.py: a temporary vault, and downloads replaced by an in-memory store.

No test touches the network or the Obsidian settings of the machine: `fetch` is swapped for a
dictionary lookup, and NEST_OBSIDIAN_CONFIG points the script at a temporary settings folder.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
from pathlib import PurePosixPath, PureWindowsPath
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import obsidian_setup as osu

KIT = Path(osu.__file__).resolve().parent.parent
PLUGIN = "sample-plugin"
OTHER = "other-plugin"
THEME = "Plain"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest(key: str, field: str, version: str) -> bytes:
    return json.dumps({field: key, "version": version}).encode()


@pytest.fixture
def store():
    """What the fake GitHub serves: url -> bytes."""
    return {}


@pytest.fixture
def calls():
    return []


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch, store, calls):
    config = tmp_path / "obsidian-config"
    config.mkdir()
    monkeypatch.setenv("NEST_OBSIDIAN_CONFIG", str(config))
    monkeypatch.setattr(osu, "obsidian_running", lambda: False)
    monkeypatch.setattr(osu, "installer_version", lambda: ())

    def fake_fetch(url: str) -> bytes:
        calls.append(url)
        if url not in store:
            raise osu.SetupError(f"download failed (404): {url}")
        return store[url]

    monkeypatch.setattr(osu, "fetch", fake_fetch)
    return config


def make_lock(tmp_path: Path, store: dict, *, min_app: str = "", with_styles: bool = True) -> Path:
    lock = {"plugins": {}, "themes": {}}
    for key in (PLUGIN, OTHER):
        files = {"main.js": f"code of {key}".encode(), "manifest.json": manifest(key, "id", "1.2.3")}
        if with_styles:
            files["styles.css"] = b".x { color: red }"
        for name, data in files.items():
            store[osu.asset_url(f"someone/{key}", "1.2.3", name)] = data
        lock["plugins"][key] = {
            "name": key.title(), "repo": f"someone/{key}", "version": "1.2.3", "minAppVersion": min_app,
            "files": {name: {"sha256": sha(data), "size": len(data)} for name, data in files.items()},
        }
    files = {"theme.css": b"body { }", "manifest.json": manifest(THEME, "name", "4.0.0")}
    for name, data in files.items():
        store[osu.asset_url("someone/plain-theme", "4.0.0", name)] = data
    lock["themes"][THEME] = {
        "repo": "someone/plain-theme", "version": "4.0.0", "minAppVersion": min_app,
        "files": {name: {"sha256": sha(data), "size": len(data)} for name, data in files.items()},
    }
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(lock), encoding="utf-8")
    return path


def make_vault(tmp_path: Path, plugins=(PLUGIN,), theme: str = THEME, settings: bool = True) -> Path:
    vault = tmp_path / "wiki"
    config = vault / ".obsidian"
    config.mkdir(parents=True)
    (config / "community-plugins.json").write_text(json.dumps(list(plugins)), encoding="utf-8")
    (config / "appearance.json").write_text(json.dumps({"cssTheme": theme, "accentColor": "#123456"}), encoding="utf-8")
    if settings:
        for key in plugins:
            folder = config / "plugins" / key
            folder.mkdir(parents=True)
            (folder / "data.json").write_text('{"mine": true}', encoding="utf-8")
    return vault


def run(*argv: str) -> int:
    return osu.main(list(argv))


def out_json(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


# --- install ---------------------------------------------------------------------------------


def test_install_writes_plugin_and_theme_and_keeps_settings(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    before = (vault / ".obsidian" / "appearance.json").read_bytes()

    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    report = out_json(capsys)

    folder = vault / ".obsidian" / "plugins" / PLUGIN
    assert (folder / "main.js").read_bytes() == b"code of sample-plugin"
    assert json.loads((folder / "manifest.json").read_text())["id"] == PLUGIN
    assert (folder / "styles.css").is_file()
    assert (folder / "data.json").read_text() == '{"mine": true}'
    assert not (folder / "data.json.bak").exists()
    assert (vault / ".obsidian" / "themes" / THEME / "theme.css").is_file()
    assert (vault / ".obsidian" / "appearance.json").read_bytes() == before
    assert json.loads((vault / ".obsidian" / "community-plugins.json").read_text()) == [PLUGIN]
    assert {r["id"]: r["status"] for r in report["results"]} == {PLUGIN: "installed", THEME: "installed"}
    assert not list(vault.rglob("*.nest-part"))


def test_install_only_what_the_vault_lists(tmp_path, store):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, plugins=(PLUGIN,))
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0
    assert not (vault / ".obsidian" / "plugins" / OTHER).exists()


def test_a_plugin_without_styles_installs(tmp_path, store):
    lock = make_lock(tmp_path, store, with_styles=False)
    vault = make_vault(tmp_path)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    assert (folder / "main.js").is_file() and not (folder / "styles.css").exists()


def test_second_run_downloads_nothing(tmp_path, store, calls, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    run("install", "--vault", str(vault), "--lock", str(lock))
    calls.clear()
    capsys.readouterr()
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    assert calls == []
    assert {r["status"] for r in out_json(capsys)["results"]} == {"present"}


def test_an_installed_plugin_of_another_version_is_left_alone(tmp_path, store):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "manifest.json").write_bytes(manifest(PLUGIN, "id", "9.9.9"))
    (folder / "main.js").write_text("the user's newer copy", encoding="utf-8")
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--only", PLUGIN) == 0
    assert (folder / "main.js").read_text() == "the user's newer copy"


def test_a_folder_that_holds_another_plugin_is_refused(tmp_path, store, calls, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "manifest.json").write_bytes(manifest("something-else", "id", "1.0.0"))
    (folder / "main.js").write_text("someone's own plugin", encoding="utf-8")
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--only", PLUGIN, "--json") == 1
    result = out_json(capsys)["results"][0]
    assert result["status"] == "refused" and "something-else" in result["reason"]
    assert calls == []
    assert json.loads((folder / "manifest.json").read_text())["id"] == "something-else"
    assert (folder / "main.js").read_text() == "someone's own plugin"
    assert sorted(p.name for p in folder.iterdir()) == ["data.json", "main.js", "manifest.json"]


def test_checksum_mismatch_writes_nothing(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, settings=False)
    store[osu.asset_url(f"someone/{PLUGIN}", "1.2.3", "main.js")] = b"tampered"

    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    report = out_json(capsys)

    assert not (vault / ".obsidian" / "plugins" / PLUGIN).exists()
    failed = next(r for r in report["results"] if r["id"] == PLUGIN)
    assert failed["status"] == "failed" and "checksum" in failed["reason"]
    # The theme is independent and still lands.
    assert (vault / ".obsidian" / "themes" / THEME / "manifest.json").is_file()


def test_failed_download_leaves_no_manifest(tmp_path, store):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    del store[osu.asset_url(f"someone/{PLUGIN}", "1.2.3", "manifest.json")]
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 1
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    assert not (folder / "manifest.json").exists()
    assert not (folder / "main.js").exists()
    assert (folder / "data.json").is_file()


def test_manifest_is_written_last(tmp_path, store, monkeypatch):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="")
    order: list[str] = []
    real_replace = osu.os.replace

    def spy(src, dst):
        order.append(Path(dst).name)
        return real_replace(src, dst)

    monkeypatch.setattr(osu.os, "replace", spy)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0
    assert order[-1] == "manifest.json" and set(order) == {"main.js", "styles.css", "manifest.json"}


def test_too_old_obsidian_skips_with_a_reason(tmp_path, store, isolated, capsys):
    lock = make_lock(tmp_path, store, min_app="1.14.0")
    vault = make_vault(tmp_path)
    (isolated / "obsidian-1.13.2.asar").write_bytes(b"")
    (isolated / "obsidian-1.9.14.asar").write_bytes(b"")

    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    report = out_json(capsys)
    assert report["obsidian"] == "1.13.2"
    assert {r["status"] for r in report["results"]} == {"skipped"}
    assert "1.14.0" in report["results"][0]["reason"]
    assert "open Obsidian once" in report["results"][0]["reason"]
    assert not (vault / ".obsidian" / "plugins" / PLUGIN / "manifest.json").exists()


def test_unknown_obsidian_version_installs_anyway(tmp_path, store, monkeypatch):
    lock = make_lock(tmp_path, store, min_app="1.14.0")
    vault = make_vault(tmp_path)
    monkeypatch.setattr(osu, "app_version", lambda: None)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0
    assert (vault / ".obsidian" / "plugins" / PLUGIN / "manifest.json").is_file()


def test_names_the_lock_does_not_know_are_reported(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, plugins=(PLUGIN, "homemade"), theme="Unknown Theme")
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    assert out_json(capsys)["unknown"] == ["homemade", "Unknown Theme"]


def test_dry_run_writes_nothing(tmp_path, store, calls):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, settings=False)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--dry-run") == 1  # as status says
    assert calls == []
    assert not (vault / ".obsidian" / "plugins").exists()


def test_a_vault_without_obsidian_settings_installs_nothing(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = tmp_path / "bare"
    vault.mkdir()
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0
    assert "nothing to install" in capsys.readouterr().out


def test_missing_vault_is_an_error(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    assert run("install", "--vault", str(tmp_path / "nope"), "--lock", str(lock)) == 1
    assert "vault folder not found" in capsys.readouterr().err


# --- the closed check ------------------------------------------------------------------------


def register(config: Path, vault: Path, *, is_open: bool) -> None:
    entry = {"path": str(vault), "ts": 1}
    if is_open:
        entry["open"] = True
    (config / "obsidian.json").write_text(json.dumps({"vaults": {"abc": entry}}), encoding="utf-8")


def test_refuses_a_vault_that_is_open(tmp_path, store, isolated, monkeypatch, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    register(isolated, vault, is_open=True)
    monkeypatch.setattr(osu, "obsidian_running", lambda: True)

    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 1
    assert "open in Obsidian" in capsys.readouterr().err
    assert not (vault / ".obsidian" / "plugins" / PLUGIN / "manifest.json").exists()

    assert run("install", "--vault", str(vault), "--lock", str(lock), "--assume-closed") == 0


def test_open_flag_counts_when_the_process_list_is_unreadable(tmp_path, store, isolated, monkeypatch):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    register(isolated, vault, is_open=True)
    monkeypatch.setattr(osu, "obsidian_running", lambda: None)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 1


def test_a_stale_open_flag_does_not_block(tmp_path, store, isolated):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    register(isolated, vault, is_open=True)  # obsidian_running() is False in these tests
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0


def test_obsidian_running_with_another_vault_does_not_block(tmp_path, store, isolated, monkeypatch):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    other = tmp_path / "elsewhere"
    other.mkdir()
    register(isolated, other, is_open=True)
    monkeypatch.setattr(osu, "obsidian_running", lambda: True)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0


def test_a_closed_registered_vault_does_not_block(tmp_path, store, isolated, monkeypatch):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    register(isolated, vault, is_open=False)
    monkeypatch.setattr(osu, "obsidian_running", lambda: True)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0


# --- restore ---------------------------------------------------------------------------------


def test_restore_puts_the_set_aside_settings_back(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "data.json.bak").write_text('{"mine": true}', encoding="utf-8")
    (folder / "data.json").write_text('{"defaults": 1}', encoding="utf-8")

    assert run("restore", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    assert out_json(capsys)["restored"] == [PLUGIN]
    assert (folder / "data.json").read_text() == '{"mine": true}'
    assert (folder / "data.json.before-restore").read_text() == '{"defaults": 1}'
    assert not (folder / "data.json.bak").exists()  # the backup is used up: restore runs once


def test_restore_when_the_plugin_wrote_no_settings(tmp_path, store):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "data.json").rename(folder / "data.json.bak")
    assert run("restore", "--vault", str(vault), "--lock", str(lock)) == 0
    assert (folder / "data.json").read_text() == '{"mine": true}'
    assert not (folder / "data.json.before-restore").exists()


def test_restore_twice_changes_nothing(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "data.json.bak").write_text('{"mine": true}', encoding="utf-8")
    assert run("restore", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    report = out_json(capsys)
    assert report["restored"] == [] and report["already_same"] == [PLUGIN]
    assert not (folder / "data.json.before-restore").exists()


def test_restore_leaves_plugins_outside_the_lock_alone(tmp_path, store):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, plugins=(PLUGIN, "homemade"))
    folder = vault / ".obsidian" / "plugins" / "homemade"
    (folder / "data.json.bak").write_text("old", encoding="utf-8")
    assert run("restore", "--vault", str(vault), "--lock", str(lock)) == 0
    assert (folder / "data.json").read_text() == '{"mine": true}'


def test_restore_refuses_an_open_vault(tmp_path, store, isolated, monkeypatch):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    register(isolated, vault, is_open=True)
    monkeypatch.setattr(osu, "obsidian_running", lambda: True)
    assert run("restore", "--vault", str(vault), "--lock", str(lock)) == 1


# --- status and vaults -----------------------------------------------------------------------


def test_status_tells_missing_from_installed(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    assert run("status", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    items = {i["id"]: i for i in out_json(capsys)["items"]}
    assert items[PLUGIN]["installed"] is None and items[PLUGIN]["settings"] is True

    run("install", "--vault", str(vault), "--lock", str(lock))
    capsys.readouterr()
    assert run("status", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    items = {i["id"]: i for i in out_json(capsys)["items"]}
    assert items[PLUGIN]["installed"] == "1.2.3" and items[THEME]["installed"] == "4.0.0"


def test_install_mentions_settings_obsidian_set_aside(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "data.json").rename(folder / "data.json.bak")
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    assert out_json(capsys)["set_aside"] == [PLUGIN]


def test_vaults_lists_what_obsidian_knows(tmp_path, isolated, capsys):
    real = tmp_path / "notes"
    (real / "sub").mkdir(parents=True)
    (real / "a.md").write_text("x", encoding="utf-8")
    (real / "sub" / "b.md").write_text("x", encoding="utf-8")
    data = {"vaults": {"1": {"path": str(real), "ts": 1, "open": True}, "2": {"path": str(tmp_path / "gone"), "ts": 2}}}
    (isolated / "obsidian.json").write_text(json.dumps(data), encoding="utf-8")

    assert run("vaults", "--json") == 0
    report = out_json(capsys)
    assert report["obsidian_found"] is True
    by_path = {v["path"]: v for v in report["vaults"]}
    assert by_path[str(real)] == {"path": str(real), "exists": True, "open": True, "notes": 2}
    assert by_path[str(tmp_path / "gone")]["exists"] is False


def test_vaults_without_obsidian(capsys):
    assert run("vaults", "--json") == 0
    assert out_json(capsys) == {"obsidian_found": False, "vaults": []}


# --- the lock file ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        lambda e: e.update(repo="https://evil.example/x"),
        lambda e: e.update(repo="../../etc"),
        lambda e: e.update(version="1.0/../../x"),
        lambda e: e["files"].update({"../../evil.js": {"sha256": "0" * 64}}),
        lambda e: e["files"]["main.js"].update(sha256="short"),
        lambda e: e["files"].pop("manifest.json"),
        lambda e: e["files"].pop("main.js"),
        lambda e: e.update(repo="../.."),
        lambda e: e.update(repo="./."),
        lambda e: e.update(repo="a/b\n"),
        lambda e: e.update(version=".."),
        lambda e: e.update(version="1..2"),
        lambda e: e.update(version="1.0\n"),
        lambda e: e.update(name={"a": 1}),
        lambda e: e.update(minAppVersion=["9"]),
        lambda e: e["files"]["main.js"].update(sha256="a" * 64 + "\n"),
    ],
)
def test_a_lock_file_with_odd_values_is_refused(tmp_path, store, change, capsys):
    lock = make_lock(tmp_path, store)
    data = json.loads(lock.read_text())
    change(data["plugins"][PLUGIN])
    lock.write_text(json.dumps(data), encoding="utf-8")
    vault = make_vault(tmp_path)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 1
    assert not (vault / ".obsidian" / "plugins" / PLUGIN / "manifest.json").exists()


def test_a_plugin_id_that_is_a_path_is_refused(tmp_path, store):
    lock = make_lock(tmp_path, store)
    data = json.loads(lock.read_text())
    data["plugins"]["../escape"] = data["plugins"][PLUGIN]
    lock.write_text(json.dumps(data), encoding="utf-8")
    assert run("status", "--vault", str(make_vault(tmp_path)), "--lock", str(lock)) == 1


def test_downloads_only_from_github(monkeypatch):
    monkeypatch.undo()  # the real fetch
    with pytest.raises(osu.SetupError):
        osu.fetch("https://example.com/main.js")
    with pytest.raises(osu.SetupError):
        osu.fetch("http://github.com/a/b/releases/download/1/main.js")


def test_version_order():
    assert osu.version_tuple("1.14.0") > osu.version_tuple("1.9.7")
    assert osu.version_tuple("1.13.0") < osu.version_tuple("1.13.1")
    assert osu.version_tuple("2.0.0-beta") == (2, 0, 0)


# --- the kit's own lock file ------------------------------------------------------------------


def test_the_kit_lock_covers_what_the_kit_configures():
    lock = osu.load_lock(KIT / "scripts" / osu.LOCK_NAME)
    ids = json.loads((KIT / "wiki" / "obsidian" / "community-plugins.json").read_text(encoding="utf-8"))
    theme = json.loads((KIT / "wiki" / "obsidian" / "appearance.json").read_text(encoding="utf-8"))["cssTheme"]
    assert set(ids) <= set(lock["plugins"])
    assert theme in lock["themes"]


def test_every_configured_plugin_with_settings_is_in_the_kit_list():
    ids = set(json.loads((KIT / "wiki" / "obsidian" / "community-plugins.json").read_text(encoding="utf-8")))
    folders = {p.parent.name for p in (KIT / "wiki" / "obsidian" / "plugins").glob("*/data.json")}
    assert folders <= ids


@pytest.mark.parametrize(
    "key",
    ["evil\n", "sample-plugin.", "sample-plugin ", " sample", ".hidden", ".. ", "...", " ", "CON", "nul", "NUL.txt",
     "com1", "LPT9.js", "a/b", "a\\b", "Sample-Plugin", "CON .x", "nul .txt", "aux .b.c", "COM1 .js", "prn  .a"],
)
def test_a_lock_key_that_is_not_a_plain_folder_name_is_refused(tmp_path, store, key):
    lock = make_lock(tmp_path, store)
    data = json.loads(lock.read_text())
    data["plugins"][key] = data["plugins"][PLUGIN]  # "Sample-Plugin": the same folder as sample-plugin on Windows
    lock.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(osu.SetupError):
        osu.load_lock(lock)


@pytest.mark.parametrize("kind", ["plugins", "themes"])
def test_a_lock_file_without_plugins_or_themes_is_refused(tmp_path, store, kind):
    lock = make_lock(tmp_path, store)
    data = json.loads(lock.read_text())
    del data[kind]
    lock.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(osu.SetupError):
        osu.load_lock(lock)


def test_a_theme_in_the_lock_must_name_theme_css(tmp_path, store):
    lock = make_lock(tmp_path, store)
    data = json.loads(lock.read_text())
    del data["themes"][THEME]["files"]["theme.css"]
    lock.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(osu.SetupError):
        osu.load_lock(lock)


def test_a_lock_file_with_the_same_key_twice_is_refused(tmp_path, store):
    lock = make_lock(tmp_path, store)
    entry = json.dumps(json.loads(lock.read_text())["plugins"][PLUGIN])
    twice = f'"{PLUGIN}": {entry}, "{PLUGIN}": {entry}'
    lock.write_text('{"plugins": {' + twice + '}, "themes": {}}', encoding="utf-8")
    with pytest.raises(osu.SetupError):
        osu.load_lock(lock)


def test_a_hostile_lock_file_is_an_error_not_a_traceback(tmp_path, store, capsys):
    lock = tmp_path / "deep.json"
    lock.write_text("[" * 100_000, encoding="utf-8")
    assert run("status", "--vault", str(make_vault(tmp_path)), "--lock", str(lock), "--json") == 1
    assert "error" in out_json(capsys)


# --- containment: nothing is written or read through a link ----------------------------------


def link(path: Path, target: Path) -> None:
    try:
        path.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        pytest.skip("this system does not let the test make a symlink")


def test_a_plugin_folder_that_is_a_link_is_refused(tmp_path, store, calls, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, settings=False)
    outside = tmp_path / "outside"
    outside.mkdir()
    (vault / ".obsidian" / "plugins").mkdir()
    link(vault / ".obsidian" / "plugins" / PLUGIN, outside)

    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    results = {r["id"]: r for r in out_json(capsys)["results"]}
    assert results[PLUGIN]["status"] == "refused" and "link" in results[PLUGIN]["reason"]
    assert list(outside.iterdir()) == []
    assert results[THEME]["status"] == "installed"  # the other item still runs
    assert not any(PLUGIN in url for url in calls)


@pytest.mark.parametrize("which", [".obsidian", "plugins", "themes"])
def test_a_linked_settings_folder_is_refused(tmp_path, store, which, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, settings=False)
    outside = tmp_path / "outside"
    if which == ".obsidian":
        (vault / ".obsidian").rename(outside)
        link(vault / ".obsidian", outside)
    else:
        outside.mkdir()
        link(vault / ".obsidian" / which, outside)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    report = out_json(capsys)
    results = {r["id"]: r["status"] for r in report["results"]}
    # A linked `.obsidian` is not even read: there is no list to work from, and both files are named.
    expected = {".obsidian": {}, "plugins": {PLUGIN: "refused", THEME: "installed"},
                "themes": {PLUGIN: "installed", THEME: "refused"}}[which]
    assert results == expected
    assert len(report["problems"]) == (2 if which == ".obsidian" else 0)
    assert not list(outside.rglob("main.js")) and not list(outside.rglob("theme.css"))


def test_a_planted_temporary_file_is_never_written_through(tmp_path, store):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="")
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    victim = tmp_path / "victim.txt"
    victim.write_text("precious", encoding="utf-8")
    for name in ("main.js.nest-part", "styles.css.nest-part", "manifest.json.nest-part"):
        link(folder / name, victim)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0
    assert victim.read_text(encoding="utf-8") == "precious"
    assert (folder / "main.js").read_bytes() == b"code of sample-plugin" and not (folder / "main.js").is_symlink()


@pytest.mark.parametrize("name", ["main.js", "styles.css", "manifest.json"])
def test_a_file_that_is_a_link_is_not_replaced_or_read(tmp_path, store, name, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="")
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    victim = tmp_path / "victim.txt"
    victim.write_bytes(manifest(PLUGIN, "id", "1.2.3"))
    before = victim.read_bytes()
    link(folder / name, victim)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    assert out_json(capsys)["results"][0]["status"] == "refused"
    assert victim.read_bytes() == before and (folder / name).is_symlink()
    assert sorted(p.name for p in folder.iterdir()) == sorted(["data.json", name])


def test_a_plugin_folder_that_is_a_file_is_a_result_not_a_traceback(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, settings=False)
    (vault / ".obsidian" / "plugins").mkdir()
    (vault / ".obsidian" / "plugins" / PLUGIN).write_text("x", encoding="utf-8")
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    results = {r["id"]: r["status"] for r in out_json(capsys)["results"]}
    assert results == {PLUGIN: "refused", THEME: "installed"}
    assert (vault / ".obsidian" / "plugins" / PLUGIN).read_text(encoding="utf-8") == "x"


def test_a_failed_write_is_a_result_and_leaves_no_temporary_file(tmp_path, store, monkeypatch, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, plugins=(PLUGIN, OTHER))
    real_replace = osu.os.replace

    def stubborn(src, dst):
        if Path(dst).parent.name == PLUGIN and Path(dst).name == "styles.css":
            raise PermissionError(13, "the file is in use", str(dst))
        return real_replace(src, dst)

    monkeypatch.setattr(osu.os, "replace", stubborn)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    results = {r["id"]: r for r in out_json(capsys)["results"]}
    assert results[PLUGIN]["status"] == "failed" and "in use" in results[PLUGIN]["reason"]
    assert results[OTHER]["status"] == "installed" and results[THEME]["status"] == "installed"
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    assert sorted(p.name for p in folder.iterdir()) == ["data.json", "main.js"]  # no manifest, no leftovers

    monkeypatch.setattr(osu.os, "replace", real_replace)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0
    assert (folder / "manifest.json").is_file()


def test_an_interrupted_write_leaves_no_temporary_file(tmp_path, store, monkeypatch):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="")

    def interrupted(src, dst):
        raise KeyboardInterrupt

    monkeypatch.setattr(osu.os, "replace", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run("install", "--vault", str(vault), "--lock", str(lock))
    assert [p.name for p in (vault / ".obsidian" / "plugins" / PLUGIN).iterdir()] == ["data.json"]


def test_an_unexpected_download_error_is_a_result(tmp_path, store, monkeypatch, capsys):
    import http.client

    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    real = osu.fetch

    def flaky(url: str) -> bytes:
        if PLUGIN in url:
            raise http.client.IncompleteRead(b"")
        return real(url)

    monkeypatch.setattr(osu, "fetch", flaky)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    results = {r["id"]: r["status"] for r in out_json(capsys)["results"]}
    assert results == {PLUGIN: "failed", THEME: "installed"}


def test_fetch_turns_a_bad_url_into_a_setup_error(monkeypatch):
    import socket

    monkeypatch.undo()  # the real fetch

    def no_network(*args, **kwargs):
        raise OSError("no network in tests")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    with pytest.raises(osu.SetupError):
        osu.fetch("https://github.com/a/b\n/releases/download/1.0/main.js")
    with pytest.raises(osu.SetupError):
        osu.fetch("https://github.com/a/b/releases/download/1.0/main.js")


def test_checksum_mismatch_on_the_last_file_writes_nothing(tmp_path, store):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, settings=False, theme="")
    store[osu.asset_url(f"someone/{PLUGIN}", "1.2.3", "manifest.json")] = b"tampered"
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 1
    assert not (vault / ".obsidian" / "plugins").exists()


# --- what counts as installed ----------------------------------------------------------------


def test_a_manifest_without_the_code_is_installed_again(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="")
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "manifest.json").write_bytes(manifest(PLUGIN, "id", "1.2.3"))
    assert run("status", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    assert out_json(capsys)["items"][0]["installed"] is None
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0
    assert (folder / "main.js").read_bytes() == b"code of sample-plugin"


def test_leftovers_of_an_interrupted_run_are_overwritten(tmp_path, store):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="")
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "main.js").write_text("half", encoding="utf-8")
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0
    assert (folder / "main.js").read_bytes() == b"code of sample-plugin"


def test_a_manifest_that_cannot_be_read_is_refused(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="")
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "manifest.json").write_text("{not json", encoding="utf-8")
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    assert out_json(capsys)["results"][0]["status"] == "refused"
    assert (folder / "manifest.json").read_text(encoding="utf-8") == "{not json"


def test_a_theme_folder_of_another_theme_is_refused(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, plugins=(), settings=False)
    folder = vault / ".obsidian" / "themes" / THEME
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_bytes(manifest("My Own", "name", "1.0.0"))
    (folder / "theme.css").write_text("mine", encoding="utf-8")
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    assert out_json(capsys)["results"][0]["status"] == "refused"
    assert (folder / "theme.css").read_text(encoding="utf-8") == "mine"


# --- exit codes and --only -------------------------------------------------------------------


@pytest.mark.parametrize("argv", [["install"], ["install", "--json"], ["bogus", "--json"], ["--json"]])
def test_a_usage_error_is_exit_2_and_json_when_asked(argv, capsys):
    with pytest.raises(SystemExit) as stop:
        run(*argv)
    assert stop.value.code == 2
    out = capsys.readouterr().out
    if "--json" in argv:
        assert "error" in json.loads(out)
    else:
        assert out == ""


def test_only_with_a_name_the_vault_does_not_ask_for_is_reported(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--only", "sample-plugni," + OTHER, "--json") == 1
    report = out_json(capsys)
    assert report["not_asked"] == [OTHER, "sample-plugni"] and report["results"] == []
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--only", "sample-plugni") == 1
    out = capsys.readouterr().out
    assert "sample-plugni" in out and "nothing to install" not in out


def test_only_with_a_name_the_lock_does_not_know_is_exit_1(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, plugins=(PLUGIN, "homemade"))
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--only", "homemade", "--json") == 1
    assert out_json(capsys)["unknown"] == ["homemade"]


def test_only_takes_a_theme_name(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--only", THEME, "--json") == 0
    assert [r["id"] for r in out_json(capsys)["results"]] == [THEME]


def test_install_and_status_agree_on_a_vault_with_a_plugin_the_lock_does_not_know(tmp_path, store):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, plugins=(PLUGIN, "homemade"))
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0
    assert run("status", "--vault", str(vault), "--lock", str(lock)) == 0
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0


def test_errors_are_json_when_asked(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    for argv in (["install", "--vault", str(tmp_path / "nope"), "--lock", str(lock)],
                 ["status", "--vault", str(tmp_path), "--lock", str(tmp_path / "no-lock")],
                 ["restore", "--vault", str(tmp_path / "nope"), "--lock", str(lock)]):
        assert run(*argv, "--json") == 1
        captured = capsys.readouterr()
        assert "error" in json.loads(captured.out) and captured.err == ""


# --- the closed check errs towards refusing --------------------------------------------------


@pytest.mark.parametrize("raw", ["{not json", "[]", '{"vaults": []}', '{"vaults": {"a": 5}}', '{"vaults": {"a": {"path": 7}}}'])
def test_an_unreadable_vault_list_blocks_unless_obsidian_is_clearly_not_running(tmp_path, store, isolated, monkeypatch, raw):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    (isolated / "obsidian.json").write_text(raw, encoding="utf-8")
    for running in (True, None):
        monkeypatch.setattr(osu, "obsidian_running", lambda answer=running: answer)
        assert run("install", "--vault", str(vault), "--lock", str(lock)) == 1
        assert not (vault / ".obsidian" / "plugins" / PLUGIN / "manifest.json").exists()
    monkeypatch.setattr(osu, "obsidian_running", lambda: False)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0


def test_no_vault_list_at_all_means_obsidian_never_ran(tmp_path, store, monkeypatch):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    monkeypatch.setattr(osu, "obsidian_running", lambda: True)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0


def test_the_open_error_does_not_invite_the_flag(tmp_path, store, isolated, monkeypatch, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    register(isolated, vault, is_open=True)
    monkeypatch.setattr(osu, "obsidian_running", lambda: True)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 1
    message = capsys.readouterr().err
    assert "confirmed" in message and "add --assume-closed" not in message


def test_dry_run_does_not_need_a_closed_vault(tmp_path, store, isolated, monkeypatch, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    register(isolated, vault, is_open=True)
    monkeypatch.setattr(osu, "obsidian_running", lambda: True)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--dry-run", "--json") == 1
    report = out_json(capsys)
    assert "error" not in report and {r["status"] for r in report["results"]} == {"would-install"}


def test_the_open_vault_is_recognised_however_its_path_is_written(tmp_path, isolated, monkeypatch):
    import unicodedata

    monkeypatch.setattr(osu, "obsidian_running", lambda: True)
    composed = unicodedata.normalize("NFC", "café-Wiki")
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    vault = tmp_path / composed
    vault.mkdir()
    register(isolated, tmp_path / decomposed, is_open=True)
    assert osu.vault_is_open(vault) is True
    register(isolated, vault, is_open=True)
    monkeypatch.chdir(tmp_path)
    for given in (composed, composed + "/", "./" + composed + "/.", str(vault).upper()):
        assert osu.vault_is_open(Path(given)) is True
    assert osu.same_path(tmp_path / "a", tmp_path / "b") is False


def test_a_link_to_the_open_vault_is_the_open_vault(tmp_path, isolated, monkeypatch):
    monkeypatch.setattr(osu, "obsidian_running", lambda: True)
    vault = tmp_path / "wiki"
    vault.mkdir()
    link(tmp_path / "shortcut", vault)
    register(isolated, vault, is_open=True)
    assert osu.vault_is_open(tmp_path / "shortcut") is True


class FakeRun:
    def __init__(self, returncode: int, stdout: str = ""):
        self.returncode, self.stdout = returncode, stdout


@pytest.mark.parametrize(
    ("system", "returncode", "stdout", "expected"),
    [
        ("mac", 0, "123\n", True),
        ("mac", 1, "", False),
        ("mac", 3, "", None),
        ("linux", 0, "123\n", True),
        ("linux", 1, "", None),  # it may run under the name electron: no proof either way
        ("windows", 0, '"Obsidian.exe","4242","Console","1","200,000 K"\n', True),
        ("windows", 0, "INFO: No tasks are running which match the specified criteria.\n", False),
        ("windows", 1, "", None),
    ],
)
def test_the_process_check_per_system(monkeypatch, system, returncode, stdout, expected):
    monkeypatch.undo()  # the real obsidian_running
    monkeypatch.setattr(osu, "system", lambda: system)
    monkeypatch.setattr(osu.shutil, "which", lambda name: "/usr/bin/" + name)
    seen: list[list[str]] = []

    def fake(command, **kwargs):
        seen.append(command)
        return FakeRun(returncode, stdout)

    monkeypatch.setattr(osu.subprocess, "run", fake)
    assert osu.obsidian_running() is expected
    assert seen[0][0] == ("tasklist" if system == "windows" else "pgrep")


def test_the_process_check_without_the_tool_knows_nothing(monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(osu, "system", lambda: "linux")
    monkeypatch.setattr(osu.shutil, "which", lambda name: None)
    assert osu.obsidian_running() is None

    def missing(command, **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(osu, "system", lambda: "windows")
    monkeypatch.setattr(osu.subprocess, "run", missing)
    assert osu.obsidian_running() is None


def test_the_settings_folders_per_system(tmp_path, monkeypatch):
    monkeypatch.delenv("NEST_OBSIDIAN_CONFIG")
    monkeypatch.setattr(osu.Path, "home", lambda: tmp_path / "Jan.de Vries")
    monkeypatch.setattr(osu, "system", lambda: "mac")
    assert osu.config_dirs() == [tmp_path / "Jan.de Vries" / "Library" / "Application Support" / "obsidian"]
    monkeypatch.setattr(osu, "system", lambda: "windows")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Jan.de Vries" / "AppData" / "Roaming"))
    assert osu.config_dirs() == [tmp_path / "Jan.de Vries" / "AppData" / "Roaming" / "obsidian"]
    monkeypatch.setattr(osu, "system", lambda: "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    dirs = osu.config_dirs()
    assert dirs[0] == tmp_path / "xdg" / "obsidian" and len(dirs) == 4


def test_any_settings_folder_can_mark_the_vault_open(tmp_path, monkeypatch):
    first, second = tmp_path / "native", tmp_path / "flatpak"
    first.mkdir()
    second.mkdir()
    vault = tmp_path / "wiki"
    vault.mkdir()
    monkeypatch.setattr(osu, "config_dirs", lambda: [first, second])
    monkeypatch.setattr(osu, "obsidian_running", lambda: True)
    (first / "obsidian.json").write_text(json.dumps({"vaults": {}}), encoding="utf-8")
    assert osu.vault_is_open(vault) is False
    register(second, vault, is_open=True)
    assert osu.vault_is_open(vault) is True


# --- restore runs once -----------------------------------------------------------------------


def test_restore_never_overwrites_an_earlier_kept_copy(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "data.json.before-restore").write_text("kept earlier", encoding="utf-8")
    (folder / "data.json.before-restore-2").write_text("kept later", encoding="utf-8")
    (folder / "data.json.bak").write_text("from the setup", encoding="utf-8")
    (folder / "data.json").write_text("three months of changes", encoding="utf-8")

    assert run("restore", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    report = out_json(capsys)
    assert report["results"] == [{"id": PLUGIN, "status": "restored", "kept": "data.json.before-restore-3"}]
    assert (folder / "data.json").read_text(encoding="utf-8") == "from the setup"
    assert (folder / "data.json.before-restore").read_text(encoding="utf-8") == "kept earlier"
    assert (folder / "data.json.before-restore-2").read_text(encoding="utf-8") == "kept later"
    assert (folder / "data.json.before-restore-3").read_text(encoding="utf-8") == "three months of changes"


def test_a_second_restore_does_not_undo_what_the_user_changed_since(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "data.json.bak").write_text("from the setup", encoding="utf-8")
    assert run("restore", "--vault", str(vault), "--lock", str(lock)) == 0
    (folder / "data.json").write_text("changed afterwards", encoding="utf-8")
    capsys.readouterr()

    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    assert out_json(capsys)["set_aside"] == []
    assert run("status", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    assert out_json(capsys)["items"][0]["set_aside"] is False
    assert run("restore", "--vault", str(vault), "--lock", str(lock)) == 0
    assert "Nothing to restore" in capsys.readouterr().out
    assert (folder / "data.json").read_text(encoding="utf-8") == "changed afterwards"
    assert (folder / "data.json.before-restore").read_text(encoding="utf-8") == '{"mine": true}'


def test_set_aside_is_only_reported_when_the_backup_differs(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="")
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "data.json.bak").write_text('{"mine": true}', encoding="utf-8")
    run("status", "--vault", str(vault), "--lock", str(lock), "--json")
    assert out_json(capsys)["items"][0]["set_aside"] is False
    (folder / "data.json.bak").write_text("something else", encoding="utf-8")
    run("status", "--vault", str(vault), "--lock", str(lock), "--json")
    assert out_json(capsys)["items"][0]["set_aside"] is True
    (folder / "data.json").unlink()
    run("status", "--vault", str(vault), "--lock", str(lock))
    assert "data.json.bak" in capsys.readouterr().out


@pytest.mark.parametrize("linked", ["data.json.bak", "data.json", "folder"])
def test_restore_refuses_links(tmp_path, store, linked, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("from outside", encoding="utf-8")
    if linked == "folder":
        (folder / "data.json").unlink()
        folder.rmdir()
        (outside / "data.json.bak").write_text("bak", encoding="utf-8")
        link(folder, outside)
    elif linked == "data.json.bak":
        link(folder / "data.json.bak", outside / "secret.txt")
    else:
        (folder / "data.json").unlink()
        link(folder / "data.json", outside / "secret.txt")
        (folder / "data.json.bak").write_text("bak", encoding="utf-8")
    before = sorted(p.name for p in outside.iterdir())

    assert run("restore", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    report = out_json(capsys)
    assert report["restored"] == [] and report["results"][0]["status"] == "failed"
    assert sorted(p.name for p in outside.iterdir()) == before
    assert (outside / "secret.txt").read_text(encoding="utf-8") == "from outside"
    if linked == "data.json.bak":
        assert (folder / "data.json").read_text(encoding="utf-8") == '{"mine": true}'


def test_one_failing_restore_does_not_stop_the_others(tmp_path, store, monkeypatch, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, plugins=(PLUGIN, OTHER))
    for key in (PLUGIN, OTHER):
        (vault / ".obsidian" / "plugins" / key / "data.json.bak").write_text("from the setup", encoding="utf-8")
    real_replace = osu.os.replace

    def stubborn(src, dst):
        if Path(dst).parent.name == OTHER:
            raise PermissionError(13, "the file is in use", str(dst))
        return real_replace(src, dst)

    monkeypatch.setattr(osu.os, "replace", stubborn)
    assert run("restore", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    report = out_json(capsys)
    assert report["restored"] == [PLUGIN]
    failed = next(r for r in report["results"] if r["id"] == OTHER)
    assert failed["status"] == "failed" and "in use" in failed["reason"]
    other = vault / ".obsidian" / "plugins" / OTHER
    assert (other / "data.json").read_text(encoding="utf-8") == '{"mine": true}'
    assert (other / "data.json.bak").is_file()


def test_restore_says_what_it_did(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "data.json.bak").write_text("from the setup", encoding="utf-8")
    assert run("restore", "--vault", str(vault), "--lock", str(lock)) == 0
    out = capsys.readouterr().out
    assert PLUGIN in out and "data.json.before-restore" in out


# --- what the second review found ------------------------------------------------------------

SCRIPT = Path(osu.__file__)


def script(*argv, config: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    """The real script in its own process: the real stdout, the real exit status, and a timeout."""
    env = {**os.environ, "NEST_OBSIDIAN_CONFIG": str(config)}
    return subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, env=env, timeout=timeout)


def snapshot(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def fifo(path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("this system has no named pipes")
    os.mkfifo(path)


# 1: set aside is only said of plugins that restore handles


def test_status_does_not_offer_restore_for_a_plugin_outside_the_lock(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, plugins=("homemade",), theme="")
    (vault / ".obsidian" / "plugins" / "homemade" / "data.json.bak").write_text("older", encoding="utf-8")
    assert run("status", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    item = out_json(capsys)["items"][0]
    assert item["set_aside"] is False and item["backup_file"] is True
    run("status", "--vault", str(vault), "--lock", str(lock))
    out = capsys.readouterr().out
    assert "data.json.bak" in out and "set aside" not in out and "restore does not handle" in out
    assert run("restore", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    assert out_json(capsys)["results"] == []


# 2: which kit plugins come with settings (the build check and PLUGINS.md say "each plugin the setup wrote
# settings for"; Style Settings ships none on purpose)


def test_the_kit_plugins_that_come_with_settings():
    folders = {p.parent.name for p in (KIT / "wiki" / "obsidian" / "plugins").glob("*/data.json")}
    assert folders == {"obsidian-minimal-settings", "templater-obsidian", "notebook-navigator",
                       "obsidian-meta-bind-plugin"}
    ids = set(json.loads((KIT / "wiki" / "obsidian" / "community-plugins.json").read_text(encoding="utf-8")))
    assert ids - folders == {"obsidian-style-settings"}
    for doc in (KIT.parent / "setup" / "build.md", KIT / "wiki" / "obsidian" / "PLUGINS.md"):
        text = " ".join(doc.read_text(encoding="utf-8").split())
        assert "each plugin the setup wrote settings for" in text, doc.name
        assert "each plugin with its settings file" not in text, doc.name


# 3: an empty --only is wrong usage, not "everything"


@pytest.mark.parametrize("only", ["", ",", " ", " , ,"])
def test_an_empty_only_is_a_usage_error(tmp_path, store, calls, capsys, only):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    with pytest.raises(SystemExit) as stop:
        run("install", "--vault", str(vault), "--lock", str(lock), "--only", only, "--json")
    assert stop.value.code == 2
    assert "error" in out_json(capsys)
    assert calls == [] and not (vault / ".obsidian" / "plugins" / PLUGIN / "manifest.json").exists()


# 4: no traceback, whatever the files and the paths hold


@pytest.mark.parametrize("path", ["bad\x00path", "x" * 5000])
def test_a_vault_list_with_a_path_that_cannot_be_compared_counts_as_unclear(tmp_path, store, isolated, monkeypatch, capsys, path):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    (isolated / "obsidian.json").write_text(json.dumps({"vaults": {"a": {"path": path, "open": True}}}), encoding="utf-8")
    monkeypatch.setattr(osu, "obsidian_running", lambda: None)
    if "\x00" in path:  # a path nobody can compare: refuse unless Obsidian is clearly not running
        assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
        assert "open in Obsidian" in out_json(capsys)["error"]
        run("status", "--vault", str(vault), "--lock", str(lock), "--json")
        assert out_json(capsys)["open"] is True
    assert run("vaults", "--json") == 0
    assert out_json(capsys)["vaults"][0]["exists"] is False
    monkeypatch.setattr(osu, "obsidian_running", lambda: False)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 0
    assert "error" not in out_json(capsys)


@pytest.mark.parametrize("command", ["status", "install"])
@pytest.mark.parametrize("as_json", [True, False])
def test_a_lone_surrogate_in_the_settings_is_printed_not_a_traceback(tmp_path, store, isolated, command, as_json):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, settings=False)
    (vault / ".obsidian" / "community-plugins.json").write_text('["\\ud800x"]', encoding="utf-8")
    (vault / ".obsidian" / "appearance.json").write_text('{"cssTheme": "\\udcff"}', encoding="utf-8")
    argv = [command, "--vault", str(vault), "--lock", str(lock)] + (["--dry-run"] if command == "install" else [])
    done = script(*argv, *(["--json"] if as_json else []), config=isolated)
    assert b"Traceback" not in done.stderr and done.returncode == 0, done.stderr
    if as_json:
        report = json.loads(done.stdout.decode("utf-8"))
        assert "\ud800x" in json.dumps(report, ensure_ascii=False)
    else:
        assert b"\\ud800x" in done.stdout


@pytest.mark.skipif(os.name == "nt", reason="a Windows command line is text, never raw bytes")
def test_a_vault_path_that_is_not_utf8_is_an_error_not_a_traceback(tmp_path, store, isolated):
    lock = make_lock(tmp_path, store)
    env = {**os.environ, "NEST_OBSIDIAN_CONFIG": str(isolated)}
    argv = [os.fsencode(sys.executable), os.fsencode(SCRIPT), b"status", b"--json", b"--vault", b"/nowhere/caf\xe9",
            b"--lock", os.fsencode(lock)]
    done = subprocess.run(argv, capture_output=True, env=env, timeout=60)
    assert done.returncode == 1 and b"Traceback" not in done.stderr, done.stderr
    assert "vault folder not found" in json.loads(done.stdout.decode("utf-8"))["error"]


def test_a_vault_path_with_a_nul_is_an_error(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    for command in ("status", "install", "restore"):
        assert run(command, "--vault", "bad\x00vault", "--lock", str(lock), "--json") == 1
        assert "error" in out_json(capsys)


# 5: nothing is read through a link, and nothing that is not a regular file is read at all


@pytest.mark.parametrize("command", ["status", "install"])
@pytest.mark.parametrize("name", ["data.json.bak", "data.json"])
def test_a_named_pipe_as_settings_file_does_not_hang(tmp_path, store, isolated, command, name):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="")
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "manifest.json").write_bytes(manifest(PLUGIN, "id", "1.2.3"))
    (folder / "main.js").write_text("code", encoding="utf-8")
    (folder / "data.json.bak").write_text("bak", encoding="utf-8")
    (folder / name).unlink()
    fifo(folder / name)
    done = script(command, "--json", "--vault", str(vault), "--lock", str(lock), config=isolated, timeout=20)
    assert b"Traceback" not in done.stderr and done.returncode == 0, done.stderr
    report = json.loads(done.stdout.decode("utf-8"))
    if command == "status":
        item = report["items"][0]
        assert item["installed"] == "1.2.3" and name in item["blocked"] and item["set_aside"] is False
    else:
        assert report["results"][0]["status"] == "present" and report["set_aside"] == []


def test_settings_are_not_compared_through_a_link(tmp_path, store, monkeypatch, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="")
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    secret = tmp_path / "secret.txt"
    secret.write_text("from outside", encoding="utf-8")
    link(folder / "data.json.bak", secret)
    opened: list[str] = []
    real = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda self: opened.append(self.name) or real(self))
    run("status", "--vault", str(vault), "--lock", str(lock), "--json")
    item = out_json(capsys)["items"][0]
    assert "data.json.bak" in item["blocked"] and "link" in item["blocked"] and item["set_aside"] is False
    assert opened == []


@pytest.mark.parametrize("name", ["community-plugins.json", "appearance.json"])
@pytest.mark.parametrize("command", ["status", "install"])
def test_a_vault_settings_file_that_is_a_link_is_not_read(tmp_path, store, calls, capsys, name, command):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, settings=False)
    elsewhere = tmp_path / "elsewhere.json"
    (vault / ".obsidian" / name).rename(elsewhere)
    link(vault / ".obsidian" / name, elsewhere)
    assert run(command, "--vault", str(vault), "--lock", str(lock), "--json") == 1
    report = out_json(capsys)
    assert any(name in line and "link" in line for line in report["problems"])
    listed = [r["id"] for r in report.get("results", report.get("items"))]
    assert listed == ([THEME] if name == "community-plugins.json" else [PLUGIN])  # the other file still counts


@pytest.mark.parametrize("command", ["status", "install", "restore"])
def test_a_linked_settings_folder_is_not_read_through(tmp_path, store, calls, capsys, command):
    lock = make_lock(tmp_path, store)
    other = make_vault(tmp_path, plugins=(PLUGIN, OTHER))
    (other / ".obsidian" / "plugins" / PLUGIN / "data.json.bak").write_text("bak", encoding="utf-8")
    vault = tmp_path / "mine"
    vault.mkdir()
    link(vault / ".obsidian", other / ".obsidian")
    before = snapshot(other)
    assert run(command, "--vault", str(vault), "--lock", str(lock), "--json") == 1
    report = out_json(capsys)
    text = json.dumps(report)
    assert ".obsidian is a link" in text and OTHER not in text  # the other vault's list was never read
    assert calls == [] and snapshot(other) == before


@pytest.mark.parametrize("command", ["status", "install"])
def test_a_named_pipe_as_plugin_list_does_not_hang(tmp_path, store, isolated, command):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, settings=False)
    (vault / ".obsidian" / "community-plugins.json").unlink()
    fifo(vault / ".obsidian" / "community-plugins.json")
    done = script(command, "--json", "--vault", str(vault), "--lock", str(lock), "--dry-run" if command == "install" else "--json",
                  config=isolated, timeout=20)
    assert done.returncode == 1 and b"Traceback" not in done.stderr
    assert any("community-plugins.json" in line for line in json.loads(done.stdout.decode("utf-8"))["problems"])


# 6: folders are made one at a time, after a check, and every write is checked again


def swapping_fetch(monkeypatch, swap) -> None:
    """Let `swap` run once, in the middle of the downloads: after the first checks, before the writes."""
    real = osu.fetch
    done: list[bool] = []

    def fetch(url: str) -> bytes:
        if not done:
            done.append(True)
            swap()
        return real(url)

    monkeypatch.setattr(osu, "fetch", fetch)


@pytest.mark.parametrize("swapped", [".obsidian", "plugins", "folder"])
def test_a_folder_swapped_for_a_link_during_the_downloads_makes_nothing_outside(tmp_path, store, monkeypatch, capsys, swapped):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="", settings=False)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    config = vault / ".obsidian"

    def swap() -> None:
        if swapped == ".obsidian":
            config.rename(vault / "moved-away")
            link(config, outside)
        elif swapped == "plugins":
            link(config / "plugins", outside)
        else:
            (config / "plugins").mkdir()
            link(config / "plugins" / PLUGIN, outside)

    swapping_fetch(monkeypatch, swap)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json", "--assume-closed") == 1
    assert out_json(capsys)["results"][0]["status"] == "refused"
    assert snapshot(outside) == ["keep.txt"]


def test_a_foreign_manifest_that_appears_during_the_downloads_is_respected(tmp_path, store, monkeypatch, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="")
    folder = vault / ".obsidian" / "plugins" / PLUGIN

    def swap() -> None:
        (folder / "manifest.json").write_text('{"id": "somebody-elses"}', encoding="utf-8")
        (folder / "main.js").write_text("their code", encoding="utf-8")

    swapping_fetch(monkeypatch, swap)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    assert out_json(capsys)["results"][0]["status"] == "refused"
    assert (folder / "main.js").read_text(encoding="utf-8") == "their code"
    assert sorted(p.name for p in folder.iterdir()) == ["data.json", "main.js", "manifest.json"]


def test_a_folder_swapped_between_two_writes_stops_the_rest(tmp_path, store, monkeypatch, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="", settings=False)
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    outside = tmp_path / "outside"
    outside.mkdir()
    real = osu.write_file
    written: list[str] = []

    def write_then_swap(target: Path, name: str, data: bytes) -> None:
        real(target, name, data)
        written.append(name)
        if len(written) == 1:
            folder.rename(vault / "moved-away")
            link(folder, outside)

    monkeypatch.setattr(osu, "write_file", write_then_swap)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    assert out_json(capsys)["results"][0]["status"] == "refused"
    assert written == ["main.js"] and snapshot(outside) == []


def test_write_file_itself_refuses_a_link_or_a_folder_in_the_place_of_the_file(tmp_path):
    folder = tmp_path / "item"
    folder.mkdir()
    victim = tmp_path / "victim.txt"
    victim.write_text("precious", encoding="utf-8")
    link(folder / "main.js", victim)
    (folder / "styles.css").mkdir()
    for name in ("main.js", "styles.css"):
        with pytest.raises(osu.Refused):
            osu.write_file(folder, name, b"new")
    assert victim.read_text(encoding="utf-8") == "precious" and (folder / "main.js").is_symlink()
    assert sorted(p.name for p in folder.iterdir()) == ["main.js", "styles.css"]  # and no temporary file


def test_a_link_this_python_cannot_recognise_is_still_refused(tmp_path, store, monkeypatch, capsys):
    """A Windows junction on a Python without os.path.isjunction: only where the folder really is tells."""
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="", settings=False)
    outside = tmp_path / "outside"
    outside.mkdir()
    (vault / ".obsidian" / "plugins").mkdir()
    link(vault / ".obsidian" / "plugins" / PLUGIN, outside)
    monkeypatch.setattr(osu, "is_link", lambda path: False)
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 1
    result = out_json(capsys)["results"][0]
    assert result["status"] == "refused" and "not inside the vault" in result["reason"]
    assert snapshot(outside) == []


def test_the_temporary_file_has_a_name_nobody_can_plant(tmp_path, store, monkeypatch):
    """Whatever the naming scheme: a link planted at the names one run used is not written through by the next."""
    lock = make_lock(tmp_path, store)
    used: list[str] = []
    real = os.replace

    def replace(src, dst):
        used.append(Path(src).name)
        real(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    first = make_vault(tmp_path / "one", theme="", settings=False)
    assert run("install", "--vault", str(first), "--lock", str(lock)) == 0
    assert len(used) == 3 and len(set(used)) == 3
    victim = tmp_path / "victim.txt"
    victim.write_text("precious", encoding="utf-8")
    second = make_vault(tmp_path / "two", theme="")
    folder = second / ".obsidian" / "plugins" / PLUGIN
    for name in used:
        link(folder / name, victim)
    assert run("install", "--vault", str(second), "--lock", str(lock)) == 0
    assert victim.read_text(encoding="utf-8") == "precious"
    assert (folder / "main.js").read_bytes() == b"code of sample-plugin"


# 7: generated lock keys: what passes is one folder, directly inside, on every system


def test_generated_lock_keys_never_leave_the_folder_or_collide(tmp_path, store):
    lock_path = make_lock(tmp_path, store)
    base = json.loads(lock_path.read_text(encoding="utf-8"))
    entry = base["plugins"][PLUGIN]
    pieces = list("abAB09 ._-/\\:*?\"<>|\n\t~$%'") + ["..", "CON", "nul", "aux", "prn", "COM1", "LPT9", "é", "ß", "\u202e"]
    rng = random.Random(20261122)
    accepted: list[str] = []
    for _ in range(4000):
        key = "".join(rng.choice(pieces) for _ in range(rng.randint(0, 5)))
        lock_path.write_text(json.dumps({"plugins": {key: entry}, "themes": {}}), encoding="utf-8")
        try:
            osu.load_lock(lock_path)
        except osu.SetupError:
            continue
        accepted.append(key)
    assert len(accepted) > 100  # the generator does reach valid names
    devices = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}
    for key in accepted:
        assert key.isascii() and key == key.strip(" ."), key
        for flavour in (PureWindowsPath("C:/v/.obsidian/plugins"), PurePosixPath("/v/.obsidian/plugins")):
            built = flavour / key
            assert built.parent == flavour and built.name == key, key
        assert key.split(".")[0].rstrip(" ").upper() not in devices, key
    distinct = sorted(set(accepted))
    by_fold: dict[str, list[str]] = {}
    for key in distinct:
        by_fold.setdefault(key.casefold(), []).append(key)
    colliding = [keys for keys in by_fold.values() if len(keys) > 1]
    assert colliding  # the generator does reach names that differ in case only
    for a, b, *_ in colliding:
        lock_path.write_text(json.dumps({"plugins": {a: entry, b: entry}, "themes": {}}), encoding="utf-8")
        with pytest.raises(osu.SetupError):
            osu.load_lock(lock_path)


# 8: exit codes of a dry run, and settings files of the wrong shape


def test_a_dry_run_with_nothing_to_do_ends_with_0(tmp_path, store):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--dry-run") == 0
    assert run("status", "--vault", str(vault), "--lock", str(lock)) == 0


@pytest.mark.parametrize(
    ("name", "body"),
    [("community-plugins.json", '{"a": 1}'), ("community-plugins.json", '"sample-plugin"'),
     ("community-plugins.json", '["sample-plugin", 5]'), ("community-plugins.json", "null"),
     ("appearance.json", "[]"), ("appearance.json", '{"cssTheme": 5}'), ("appearance.json", '"Plain"')],
)
def test_a_settings_file_of_the_wrong_shape_is_named(tmp_path, store, calls, capsys, name, body):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, settings=False)
    (vault / ".obsidian" / name).write_text(body, encoding="utf-8")
    for command in ("status", "install"):
        assert run(command, "--vault", str(vault), "--lock", str(lock), "--json") == 1
        assert any(name in line for line in out_json(capsys)["problems"])
        assert run(command, "--vault", str(vault), "--lock", str(lock)) == 1
        assert name in capsys.readouterr().out


def test_a_vault_with_sound_settings_has_no_problems(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    (vault / ".obsidian" / "appearance.json").write_text('{"accentColor": "#123456"}', encoding="utf-8")  # no theme: fine
    for command in ("install", "status"):
        assert run(command, "--vault", str(vault), "--lock", str(lock), "--json") == 0
        assert out_json(capsys)["problems"] == []


# 9: install clears its own leftovers, and only those


def test_stale_temporary_files_of_an_earlier_run_are_removed(tmp_path, store):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, theme="")
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    victim = tmp_path / "victim.txt"
    victim.write_text("precious", encoding="utf-8")
    (folder / ".nest-abc123.part").write_text("half a file", encoding="utf-8")
    link(folder / ".nest-linked.part", victim)
    (folder / ".nest-folder.part").mkdir()
    (folder / "nest-notes.part").write_text("the user's", encoding="utf-8")
    (folder / ".nest-other.txt").write_text("the user's", encoding="utf-8")
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 0
    assert sorted(p.name for p in folder.iterdir()) == [
        ".nest-folder.part", ".nest-linked.part", ".nest-other.txt", "data.json", "main.js", "manifest.json",
        "nest-notes.part", "styles.css"]
    assert victim.read_text(encoding="utf-8") == "precious"
