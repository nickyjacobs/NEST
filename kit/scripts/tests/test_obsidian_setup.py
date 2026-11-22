"""Tests for obsidian_setup.py: a temporary vault, and downloads replaced by an in-memory store.

No test touches the network or the Obsidian settings of the machine: `fetch` is swapped for a
dictionary lookup, and NEST_OBSIDIAN_CONFIG points the script at a temporary settings folder.
"""
from __future__ import annotations

import hashlib
import json
import sys
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


def test_a_manifest_of_another_plugin_does_not_count_as_installed(tmp_path, store):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path)
    folder = vault / ".obsidian" / "plugins" / PLUGIN
    (folder / "manifest.json").write_bytes(manifest("something-else", "id", "1.0.0"))
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--only", PLUGIN) == 0
    assert json.loads((folder / "manifest.json").read_text())["id"] == PLUGIN


def test_checksum_mismatch_writes_nothing(tmp_path, store, capsys):
    lock = make_lock(tmp_path, store)
    vault = make_vault(tmp_path, settings=False)
    store[osu.asset_url(f"someone/{PLUGIN}", "1.2.3", "main.js")] = b"tampered"

    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 2
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
    assert run("install", "--vault", str(vault), "--lock", str(lock)) == 2
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

    assert run("install", "--vault", str(vault), "--lock", str(lock), "--json") == 2
    report = out_json(capsys)
    assert report["obsidian"] == "1.13.2"
    assert {r["status"] for r in report["results"]} == {"skipped"}
    assert "1.14.0" in report["results"][0]["reason"]
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
    assert run("install", "--vault", str(vault), "--lock", str(lock), "--dry-run") == 0
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
    assert (folder / "data.json.bak").is_file()


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
    assert run("status", "--vault", str(vault), "--lock", str(lock), "--json") == 2
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
