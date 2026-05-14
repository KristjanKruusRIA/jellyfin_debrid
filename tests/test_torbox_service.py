"""Tests for TorBox debrid provider behavior."""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _load_torbox_module(monkeypatch):
    """Load torbox module directly to avoid package import side-effects."""
    repo_root = Path(__file__).resolve().parents[1]
    torbox_path = str(repo_root / "debrid" / "services" / "torbox.py")

    import sys

    ui_print_stub = ModuleType("ui.ui_print")
    ui_print_stub.ui_settings = SimpleNamespace(debug=True)
    ui_print_logs = []

    def ui_print_fn(*a, **k):
        ui_print_logs.append((a, k))

    ui_print_stub.ui_print = ui_print_fn
    monkeypatch.setitem(sys.modules, "ui.ui_print", ui_print_stub)

    releases_stub = ModuleType("releases")
    releases_stub.sort = SimpleNamespace(unwanted=[])
    monkeypatch.setitem(sys.modules, "releases", releases_stub)

    downloader_stub = ModuleType("downloader")
    monkeypatch.setitem(sys.modules, "downloader", downloader_stub)

    spec = importlib.util.spec_from_file_location("torbox_test", torbox_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module, ui_print_logs


def test_check_marks_only_cached_hashes(monkeypatch):
    torbox, _logs = _load_torbox_module(monkeypatch)

    def fake_get(path, params=None, context=None):
        assert path == "/v1/api/torrents/checkcached"
        return SimpleNamespace(
            success=True,
            data={
                "a" * 40: True,
                "b" * 40: False,
            },
        )

    monkeypatch.setattr(torbox, "get", fake_get)

    element = SimpleNamespace(
        Releases=[
            SimpleNamespace(hash="a" * 40, title="cached", size=2, files=[], cached=[]),
            SimpleNamespace(
                hash="b" * 40,
                title="uncached",
                size=1,
                files=[],
                cached=[],
            ),
        ]
    )

    torbox.check(element)

    assert len(element.Releases) == 1
    assert element.Releases[0].title == "cached"
    assert "TB" in element.Releases[0].cached


def test_check_keeps_http_releases(monkeypatch):
    torbox, _logs = _load_torbox_module(monkeypatch)
    monkeypatch.setattr(
        torbox,
        "get",
        lambda *args, **kwargs: SimpleNamespace(success=True, data={}),
    )

    element = SimpleNamespace(
        Releases=[
            SimpleNamespace(
                hash="",
                title="HTTP release",
                type="http",
                size=7,
                files=["keep"],
                cached=[],
            )
        ]
    )

    torbox.check(element)

    assert len(element.Releases) == 1
    assert "TB" in element.Releases[0].cached


def test_download_preserves_http_release_size_for_downloader(monkeypatch):
    torbox, _logs = _load_torbox_module(monkeypatch)
    captured = {}

    def fake_download_from_realdebrid(release, element):
        captured["size"] = release.size
        return False

    monkeypatch.setattr(
        torbox.downloader,
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
        cached=["TB"],
    )
    element = SimpleNamespace(Releases=[release], deviation=lambda: r"(.*)")

    result = torbox.download(element, force=True)

    assert result is False
    assert captured["size"] == 11.9


def test_download_torrent_requests_links_and_calls_downloader(monkeypatch):
    torbox, _logs = _load_torbox_module(monkeypatch)

    def fake_post(path, data=None, files=None, context=None):
        assert path == "/v1/api/torrents/createtorrent"
        return SimpleNamespace(success=True, data={"id": 42})

    def fake_get(path, params=None, context=None):
        if path == "/v1/api/torrents/mylist":
            return SimpleNamespace(
                success=True,
                data={
                    "id": 42,
                    "files": [
                        {"id": 1, "name": "movie.mkv"},
                    ],
                },
            )
        if path == "/v1/api/torrents/requestdl":
            return SimpleNamespace(success=True, data={"download": "https://cdn/x"})
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(torbox, "post", fake_post)
    monkeypatch.setattr(torbox, "get", fake_get)
    monkeypatch.setattr(torbox, "api_key", "test-token")

    called = {"count": 0}

    def fake_download_from_realdebrid(release, element):
        called["count"] += 1
        assert release.download == ["https://cdn/x"]
        assert release.filenames == ["movie.mkv"]
        return True

    monkeypatch.setattr(
        torbox.downloader,
        "download_from_realdebrid",
        fake_download_from_realdebrid,
        raising=False,
    )

    element = SimpleNamespace(
        Releases=[
            SimpleNamespace(
                title="Movie 2026 1080p",
                type="magnet",
                size=10,
                files=[],
                download=["magnet:?xt=urn:btih:" + "a" * 40 + "&dn=movie"],
                cached=["TB"],
            )
        ],
        deviation=lambda: r"(.*)",
        query=lambda: "movie.2026",
        type="movie",
    )

    debrid_stub = ModuleType("debrid")
    debrid_stub.downloading = []
    monkeypatch.setitem(__import__("sys").modules, "debrid", debrid_stub)

    assert torbox.download(element, force=True) is True
    assert called["count"] == 1
