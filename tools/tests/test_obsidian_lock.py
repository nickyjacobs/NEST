"""Tests for obsidian_lock.py: upstream is a dictionary, nothing touches the network."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import obsidian_lock as ol

REPO_ROOT = Path(ol.__file__).resolve().parent.parent


class Upstream:
    """A fake GitHub: per repository a manifest at HEAD and the files of its release."""

    def __init__(self):
        self.head: dict[str, dict] = {}
        self.release: dict[str, dict[str, bytes]] = {}
        self.calls: list[str] = []
        for key, repo in ol.PLUGINS.items():
            self.add(repo, {"id": key, "name": key.title(), "version": "1.0.0", "minAppVersion": "1.5.0"},
                     {"main.js": b"code of " + key.encode(), "styles.css": b"css"})
        for key, repo in ol.THEMES.items():
            self.add(repo, {"name": key, "version": "2.0.0", "minAppVersion": "1.6.0"}, {"theme.css": b"theme"})

    def add(self, repo: str, manifest: dict, files: dict[str, bytes]) -> None:
        self.head[repo] = manifest
        self.release[repo] = {**files, "manifest.json": json.dumps(manifest).encode()}

    def get(self, url: str) -> bytes | None:
        self.calls.append(url)
        if url.startswith("https://raw.githubusercontent.com/"):
            repo = "/".join(url.split("/")[3:5])
            return json.dumps(self.head[repo]).encode()
        repo = "/".join(url.split("/")[3:5])
        version, name = url.split("/")[-2:]
        if version != self.head[repo]["version"] and version != json.loads(self.release[repo]["manifest.json"])["version"]:
            return None
        return self.release[repo].get(name)


@pytest.fixture
def upstream(tmp_path, monkeypatch):
    fake = Upstream()
    monkeypatch.setattr(ol, "get", fake.get)
    monkeypatch.setattr(ol, "ROOT", tmp_path)
    monkeypatch.setattr(ol, "LOCK", tmp_path / "obsidian.lock.json")
    return fake


def run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["obsidian_lock.py", *argv])
    return ol.main()


def test_the_tables_match_what_the_kit_configures():
    obsidian = REPO_ROOT / "kit" / "wiki" / "obsidian"
    ids = json.loads((obsidian / "community-plugins.json").read_text(encoding="utf-8"))
    theme = json.loads((obsidian / "appearance.json").read_text(encoding="utf-8"))["cssTheme"]
    assert sorted(ol.PLUGINS) == sorted(ids)
    assert list(ol.THEMES) == [theme]


def test_the_kit_lock_file_has_exactly_the_tables_entries_and_repositories():
    lock = json.loads((REPO_ROOT / "kit" / "scripts" / "obsidian.lock.json").read_text(encoding="utf-8"))
    assert {key: entry["repo"] for key, entry in lock["plugins"].items()} == ol.PLUGINS
    assert {key: entry["repo"] for key, entry in lock["themes"].items()} == ol.THEMES


def test_writes_the_checksum_of_the_bytes_it_downloaded(upstream, monkeypatch, capsys):
    assert run(monkeypatch) == 0
    lock = json.loads(ol.LOCK.read_text(encoding="utf-8"))
    for key, repo in ol.PLUGINS.items():
        entry = lock["plugins"][key]
        assert entry["repo"] == repo and entry["version"] == "1.0.0" and entry["minAppVersion"] == "1.5.0"
        assert set(entry["files"]) == {"main.js", "styles.css", "manifest.json"}
        for name, meta in entry["files"].items():
            data = upstream.release[repo][name]
            assert meta == {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    assert set(lock["themes"]["Minimal"]["files"]) == {"theme.css", "manifest.json"}


def test_the_released_manifest_is_downloaded_once(upstream, monkeypatch, capsys):
    assert run(monkeypatch) == 0
    for repo in [*ol.PLUGINS.values(), *ol.THEMES.values()]:
        asked = [u for u in upstream.calls if u.startswith(f"https://github.com/{repo}/") and u.endswith("/manifest.json")]
        assert len(asked) == 1


def test_a_plugin_without_styles_is_locked_without_them(upstream, monkeypatch, capsys):
    del upstream.release["SilentVoid13/Templater"]["styles.css"]
    assert run(monkeypatch) == 0
    lock = json.loads(ol.LOCK.read_text(encoding="utf-8"))
    assert set(lock["plugins"]["templater-obsidian"]["files"]) == {"main.js", "manifest.json"}


def test_check_is_quiet_when_nothing_changed(upstream, monkeypatch, capsys):
    assert run(monkeypatch) == 0
    before = ol.LOCK.read_bytes()
    capsys.readouterr()
    assert run(monkeypatch, "--check") == 0
    assert "up to date" in capsys.readouterr().out
    assert ol.LOCK.read_bytes() == before


def test_check_sees_a_newer_version(upstream, monkeypatch, capsys):
    assert run(monkeypatch) == 0
    repo = ol.PLUGINS["templater-obsidian"]
    upstream.add(repo, {"id": "templater-obsidian", "version": "1.1.0"}, {"main.js": b"new"})
    capsys.readouterr()
    assert run(monkeypatch, "--check") == 1
    assert "templater-obsidian: 1.0.0 -> 1.1.0" in capsys.readouterr().out


def test_check_sees_a_file_replaced_under_the_same_version(upstream, monkeypatch, capsys):
    assert run(monkeypatch) == 0
    upstream.release[ol.PLUGINS["templater-obsidian"]]["main.js"] = b"replaced upstream under the same tag"
    capsys.readouterr()
    assert run(monkeypatch, "--check") == 1
    out = capsys.readouterr().out
    assert "templater-obsidian" in out and "main.js changed upstream" in out


def test_check_sees_an_entry_that_left_or_joined_the_table(upstream, monkeypatch, capsys):
    assert run(monkeypatch) == 0
    without = {k: v for k, v in ol.PLUGINS.items() if k != "templater-obsidian"}
    monkeypatch.setattr(ol, "PLUGINS", without)
    capsys.readouterr()
    assert run(monkeypatch, "--check") == 1
    assert "templater-obsidian: in the lock file" in capsys.readouterr().out

    assert run(monkeypatch) == 0  # the lock file now lacks it
    monkeypatch.undo()
    monkeypatch.setattr(ol, "get", upstream.get)
    lock = json.loads(json.dumps({"plugins": {}, "themes": {}}))
    assert any("none -> 1.0.0" in line for line in ol.differences(lock, ol.build()))


def test_a_manifest_for_another_plugin_stops_the_run(upstream, monkeypatch):
    repo = ol.PLUGINS["templater-obsidian"]
    upstream.head[repo] = {"id": "something-else", "version": "1.0.0"}
    with pytest.raises(SystemExit) as stop:
        run(monkeypatch)
    assert "something-else" in str(stop.value)
    assert not ol.LOCK.exists()


def test_a_release_whose_manifest_differs_from_the_repository_stops_the_run(upstream, monkeypatch):
    repo = ol.PLUGINS["templater-obsidian"]
    upstream.release[repo]["manifest.json"] = json.dumps({"id": "templater-obsidian", "version": "0.9.0"}).encode()
    upstream.head[repo]["version"] = "1.0.0"
    with pytest.raises(SystemExit):
        run(monkeypatch)
    assert not ol.LOCK.exists()


@pytest.mark.parametrize("version", ["1.0/../x", "..", "1.0\n", "", None, 3])
def test_a_version_the_installer_would_refuse_is_not_locked(upstream, monkeypatch, version):
    upstream.head[ol.PLUGINS["templater-obsidian"]]["version"] = version
    with pytest.raises(SystemExit):
        run(monkeypatch)
    assert not ol.LOCK.exists()


def test_a_missing_required_file_stops_the_run(upstream, monkeypatch):
    del upstream.release[ol.PLUGINS["templater-obsidian"]]["main.js"]
    with pytest.raises(SystemExit) as stop:
        run(monkeypatch)
    assert "main.js" in str(stop.value)


class FakeResponse:
    def __init__(self, size: int):
        self.size = size

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, amount: int) -> bytes:
        return b"x" * min(amount, self.size)


def test_a_download_over_the_cap_stops_the_run(monkeypatch):
    monkeypatch.setattr(ol, "MAX_BYTES", 10)
    monkeypatch.setattr(ol.urllib.request, "urlopen", lambda request, timeout: FakeResponse(11))
    with pytest.raises(SystemExit):
        ol.get("https://github.com/a/b/releases/download/1/main.js")
    monkeypatch.setattr(ol.urllib.request, "urlopen", lambda request, timeout: FakeResponse(10))
    assert ol.get("https://github.com/a/b/releases/download/1/main.js") == b"x" * 10
