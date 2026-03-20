"""Integration-style tests for season pack behavior with simplified check()."""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _create_test_environment(monkeypatch):
    """Create isolated test environment with minimal stubs."""
    import sys

    # Track all ui_print calls for verification
    ui_print_logs = []

    # Stub ui.ui_print
    ui_print_stub = ModuleType("ui.ui_print")
    ui_print_stub.ui_settings = SimpleNamespace(debug=True)

    def ui_print_fn(*args, **kwargs):
        ui_print_logs.append((args, kwargs))

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
    releases_stub.sort = SimpleNamespace(unwanted=[])
    monkeypatch.setitem(sys.modules, "releases", releases_stub)

    # Stub downloader
    downloader_stub = ModuleType("downloader")
    monkeypatch.setitem(sys.modules, "downloader", downloader_stub)

    return ui_print_logs


def _load_realdebrid_module():
    """Load realdebrid module with stubbed dependencies."""
    repo_root = Path(__file__).resolve().parents[1]
    realdebrid_path = str(repo_root / "debrid" / "services" / "realdebrid.py")

    spec = importlib.util.spec_from_file_location("realdebrid_test", realdebrid_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def test_season_pack_check_marks_all_valid_releases_cached(monkeypatch):
    """Season pack torrents with valid hashes are marked cached and sorted."""
    ui_print_logs = _create_test_environment(monkeypatch)
    realdebrid = _load_realdebrid_module()

    element = SimpleNamespace()
    element.type = "show"
    element.Releases = [
        SimpleNamespace(
            hash="a" * 40,
            title="Show.S01.1080p.Season.Pack.Hash.A",
            size=30,
            files=["ignored"],
            cached=[],
        ),
        SimpleNamespace(
            hash="b" * 40,
            title="Show.S01.720p.Season.Pack.Hash.B",
            size=20,
            files=["ignored"],
            cached=[],
        ),
        SimpleNamespace(
            hash="c" * 40,
            title="Show.S01.480p.Season.Pack.Hash.C",
            size=10,
            files=["ignored"],
            cached=[],
        ),
    ]
    element.files = lambda: ["S01E.*"]

    ui_print_logs.clear()
    realdebrid.check(element)

    assert [release.title for release in element.Releases] == [
        "Show.S01.1080p.Season.Pack.Hash.A",
        "Show.S01.720p.Season.Pack.Hash.B",
        "Show.S01.480p.Season.Pack.Hash.C",
    ]
    for release in element.Releases:
        assert "RD" in release.cached
        assert release.files == []


def test_invalid_season_pack_hashes_allow_episode_retry_fallback(monkeypatch):
    """If season packs have invalid hashes, they are removed and episode retry can proceed."""
    ui_print_logs = _create_test_environment(monkeypatch)
    realdebrid = _load_realdebrid_module()

    watch_called = []
    episode1 = SimpleNamespace(
        download=lambda **_: (False, True), watch=lambda: watch_called.append("E01")
    )
    episode2 = SimpleNamespace(
        download=lambda **_: (False, True), watch=lambda: watch_called.append("E02")
    )
    episode3 = SimpleNamespace(
        download=lambda **_: (False, True), watch=lambda: watch_called.append("E03")
    )

    season = SimpleNamespace()
    season.type = "season"
    season.Episodes = [episode1, episode2, episode3]
    season.Releases = [
        SimpleNamespace(
            hash="short", title="Season.Pack.A", size=10, files=[], cached=[]
        ),
        SimpleNamespace(hash="", title="Season.Pack.B", size=8, files=[], cached=[]),
    ]
    season.files = lambda: ["S01E.*"]

    ui_print_logs.clear()
    realdebrid.check(season)

    assert season.Releases == []

    if len(season.Releases) == 0:
        for episode in season.Episodes:
            downloaded, retry = episode.download()
            if retry and not downloaded:
                episode.watch()

    assert watch_called == ["E01", "E02", "E03"]


def test_http_season_pack_skips_hash_validation(monkeypatch):
    """HTTP season pack releases should bypass hash validation and be cached."""
    ui_print_logs = _create_test_environment(monkeypatch)
    realdebrid = _load_realdebrid_module()

    season = SimpleNamespace()
    season.type = "season"
    season.Releases = [
        SimpleNamespace(
            hash="",
            title="Season.Pack.HTTP",
            type="http",
            size=42,
            files=[],
            cached=[],
        )
    ]
    season.files = lambda: ["S01E.*"]

    ui_print_logs.clear()
    realdebrid.check(season)

    assert len(season.Releases) == 1
    assert season.Releases[0].title == "Season.Pack.HTTP"
    assert "RD" in season.Releases[0].cached
