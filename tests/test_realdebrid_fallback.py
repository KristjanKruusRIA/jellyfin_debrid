"""Tests for simplified RealDebrid cache marking in check()."""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _load_realdebrid_module(monkeypatch):
    """Load realdebrid module directly to avoid package import side-effects."""
    repo_root = Path(__file__).resolve().parents[1]
    realdebrid_path = str(repo_root / "debrid" / "services" / "realdebrid.py")

    # Inject minimal stubs to avoid importing large package graph
    import sys

    # Stub ui.ui_print
    ui_print_stub = ModuleType("ui.ui_print")
    ui_print_stub.ui_settings = SimpleNamespace(debug=True)
    ui_print_logs = []

    def ui_print_fn(*a, **k):
        ui_print_logs.append((a, k))

    ui_print_stub.ui_print = ui_print_fn
    monkeypatch.setitem(sys.modules, "ui.ui_print", ui_print_stub)

    # Stub releases module
    releases_stub = ModuleType("releases")

    class _Release:
        def __init__(self, source, type_, title, files, size, download, seeders=0):
            self.source = source
            self.type = type_
            self.title = title
            self.files = files
            self.size = size
            self.download = download
            self.seeders = seeders
            self.hash = ""
            self.cached = []
            self.checked = False
            self.wanted = 0
            self.unwanted = 0

    releases_stub.release = _Release
    releases_stub.sort = SimpleNamespace(unwanted=[])  # Add sort.unwanted stub
    monkeypatch.setitem(sys.modules, "releases", releases_stub)

    # Stub downloader
    downloader_stub = ModuleType("downloader")
    monkeypatch.setitem(sys.modules, "downloader", downloader_stub)

    spec = importlib.util.spec_from_file_location("realdebrid_test", realdebrid_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module, ui_print_logs


def test_check_marks_torrent_releases_as_cached(monkeypatch):
    """Valid torrent releases should all be marked cached by RD."""
    realdebrid, ui_print_logs = _load_realdebrid_module(monkeypatch)
    element = SimpleNamespace()
    element.Releases = [
        SimpleNamespace(
            hash="a" * 40, title="Release 1", size=1, files=["ignored"], cached=[]
        ),
        SimpleNamespace(
            hash="b" * 40, title="Release 2", size=2, files=["ignored"], cached=[]
        ),
    ]
    element.files = lambda: [".*"]

    ui_print_logs.clear()
    realdebrid.check(element)

    assert len(element.Releases) == 2
    for release in element.Releases:
        assert "RD" in release.cached
        assert release.files == []


def test_check_removes_releases_without_valid_hash(monkeypatch):
    """Releases missing a 40-char hash should be removed."""
    realdebrid, ui_print_logs = _load_realdebrid_module(monkeypatch)
    element = SimpleNamespace()
    element.Releases = [
        SimpleNamespace(hash="a" * 40, title="valid", size=100, files=[], cached=[]),
        SimpleNamespace(
            hash="short", title="invalid-short", size=10, files=[], cached=[]
        ),
        SimpleNamespace(hash="", title="invalid-empty", size=1, files=[], cached=[]),
    ]
    element.files = lambda: [".*"]

    ui_print_logs.clear()
    realdebrid.check(element)

    assert len(element.Releases) == 1
    assert element.Releases[0].title == "valid"
    assert "RD" in element.Releases[0].cached


def test_check_skips_http_releases(monkeypatch):
    """HTTP releases should skip hash validation and still be marked cached."""
    realdebrid, ui_print_logs = _load_realdebrid_module(monkeypatch)
    element = SimpleNamespace()
    element.Releases = [
        SimpleNamespace(
            hash="",
            title="HTTP Release",
            type="http",
            size=50,
            files=["keep"],
            cached=[],
        ),
        SimpleNamespace(
            hash="a" * 40, title="Torrent Release", size=10, files=[], cached=[]
        ),
    ]
    element.files = lambda: [".*"]

    ui_print_logs.clear()
    realdebrid.check(element)

    assert len(element.Releases) == 2
    http_release = next(r for r in element.Releases if r.title == "HTTP Release")
    torrent_release = next(r for r in element.Releases if r.title == "Torrent Release")
    assert "RD" in http_release.cached
    assert "RD" in torrent_release.cached


def test_check_sorts_by_size(monkeypatch):
    """Releases should be sorted by size descending after check()."""
    realdebrid, ui_print_logs = _load_realdebrid_module(monkeypatch)
    element = SimpleNamespace()
    element.Releases = [
        SimpleNamespace(hash="a" * 40, title="small", size=1, files=[], cached=[]),
        SimpleNamespace(hash="b" * 40, title="large", size=10, files=[], cached=[]),
        SimpleNamespace(hash="c" * 40, title="medium", size=5, files=[], cached=[]),
    ]
    element.files = lambda: [".*"]

    ui_print_logs.clear()
    realdebrid.check(element)

    assert [r.title for r in element.Releases] == ["large", "medium", "small"]


def test_check_makes_no_network_calls(monkeypatch):
    """check() must not call get() or post() — no RD API calls."""
    realdebrid, ui_print_logs = _load_realdebrid_module(monkeypatch)

    def fail_get(*a, **kw):
        raise AssertionError("check() should not call get()")

    def fail_post(*a, **kw):
        raise AssertionError("check() should not call post()")

    monkeypatch.setattr(realdebrid, "get", fail_get)
    monkeypatch.setattr(realdebrid, "post", fail_post)

    element = SimpleNamespace()
    element.Releases = [
        SimpleNamespace(hash="a" * 40, title="Release 1", size=5, files=[], cached=[]),
    ]
    element.files = lambda: [".*"]

    # Should not raise
    realdebrid.check(element)
    assert "RD" in element.Releases[0].cached


def test_download_preserves_http_release_size_for_downloader(monkeypatch):
    """HTTP releases should keep their scraped size when handed to downloader."""
    realdebrid, _ui_print_logs = _load_realdebrid_module(monkeypatch)
    captured: dict[str, float] = {}

    def fake_download_from_realdebrid(release, element):
        captured["size"] = release.size
        return False

    monkeypatch.setattr(
        realdebrid.downloader,
        "download_from_realdebrid",
        fake_download_from_realdebrid,
        raising=False,
    )

    release = SimpleNamespace(
        title="HTTP Release",
        type="http",
        size=11.9,
        files=[],
        download=["https://example.invalid/video.mkv"],
        cached=["RD"],
    )
    element = SimpleNamespace(
        Releases=[release],
        deviation=lambda: r"(.*)",
    )

    result = realdebrid.download(element, force=True)

    assert result is False
    assert captured["size"] == 11.9
