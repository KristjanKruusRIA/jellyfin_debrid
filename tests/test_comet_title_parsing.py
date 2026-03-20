"""Tests for Comet title parsing — ensures torrent names are extracted correctly."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _import_comet(monkeypatch):
    """Load comet.py in isolation with stubbed dependencies."""
    repo_root = Path(__file__).resolve().parents[1]
    comet_path = repo_root / "scraper" / "services" / "comet.py"

    # Remove cached modules
    for mod_name in [
        "scraper",
        "scraper.services",
        "scraper.services.comet",
        "ui",
        "ui.ui_print",
        "releases",
        "base",
    ]:
        sys.modules.pop(mod_name, None)

    # Stub: ui
    logs = []

    ui_pkg = ModuleType("ui")
    ui_pkg.__path__ = []
    ui_print_mod = ModuleType("ui.ui_print")
    ui_settings_stub = SimpleNamespace(debug="true", log="false")

    def ui_print_fn(*args, **kwargs):
        logs.append((args, kwargs))

    setattr(ui_print_mod, "ui_print", ui_print_fn)
    setattr(ui_print_mod, "ui_settings", ui_settings_stub)
    setattr(ui_pkg, "ui_print", ui_print_mod)
    setattr(ui_pkg, "ui_settings", ui_settings_stub)
    monkeypatch.setitem(sys.modules, "ui", ui_pkg)
    monkeypatch.setitem(sys.modules, "ui.ui_print", ui_print_mod)

    # Stub: releases
    class FakeRelease:
        def __init__(self, source, type_, title, files, size, download, seeders=0):
            self.source = source
            self.type = type_
            self.title = title
            self.files = files
            self.size = size
            self.download = download
            self.seeders = seeders

    releases_mod = ModuleType("releases")
    setattr(releases_mod, "release", FakeRelease)
    monkeypatch.setitem(sys.modules, "releases", releases_mod)

    # Stub: base (provides SimpleNamespace, copy, custom_session, json, regex, time)
    import copy
    import json
    import time

    import regex
    import requests

    base_mod = ModuleType("base")
    setattr(base_mod, "SimpleNamespace", SimpleNamespace)
    setattr(base_mod, "copy", copy)
    setattr(base_mod, "json", json)
    setattr(base_mod, "regex", regex)
    setattr(base_mod, "time", time)
    setattr(base_mod, "custom_session", requests.Session)
    monkeypatch.setitem(sys.modules, "base", base_mod)

    # Stub: scraper.services (provides active)
    scraper_pkg = ModuleType("scraper")
    scraper_pkg.__path__ = [str(repo_root / "scraper")]
    services_mod = ModuleType("scraper.services")
    setattr(services_mod, "active", ["comet"])
    setattr(scraper_pkg, "services", services_mod)
    monkeypatch.setitem(sys.modules, "scraper", scraper_pkg)
    monkeypatch.setitem(sys.modules, "scraper.services", services_mod)

    # Load comet module
    spec = importlib.util.spec_from_file_location("scraper.services.comet", comet_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "scraper.services.comet", module)
    spec.loader.exec_module(module)
    return module, logs


def _make_stream(**kwargs):
    """Build a fake Stremio stream object."""
    return SimpleNamespace(**kwargs)


def test_title_from_behavior_hints_filename(monkeypatch):
    """behaviorHints.filename should be preferred over title/name."""
    comet, logs = _import_comet(monkeypatch)
    comet.base_url = "http://localhost"
    comet.b64config = "test"

    stream = _make_stream(
        infoHash="a" * 40,
        title="[RD] Comet 2160p",
        name="[RD+] Comet\n2160p | 14.6 GB",
        behaviorHints=SimpleNamespace(
            filename="The.Strangers.Chapter.3.2026.2160p.WEB-DL.H265-GROUP.mkv"
        ),
        size="15695765913",
    )
    response = SimpleNamespace(streams=[stream])
    monkeypatch.setattr(comet, "get", lambda url: response)

    results = comet.scrape("tt1234567", "tt1234567")
    assert len(results) == 1
    assert results[0].title == "The.Strangers.Chapter.3.2026.2160p.WEB-DL.H265-GROUP"


def test_title_from_description_first_line(monkeypatch):
    """First line of description should be used when behaviorHints is absent."""
    comet, logs = _import_comet(monkeypatch)
    comet.base_url = "http://localhost"
    comet.b64config = "test"

    stream = _make_stream(
        infoHash="b" * 40,
        title="[RD] Comet 1080p",
        name="[RD+] Comet\n1080p",
        description="The.Movie.2026.1080p.BluRay.x264-SPARKS\n📦 14.6 GB",
        size="15695765913",
    )
    response = SimpleNamespace(streams=[stream])
    monkeypatch.setattr(comet, "get", lambda url: response)

    results = comet.scrape("tt1234567", "tt1234567")
    assert len(results) == 1
    assert results[0].title == "The.Movie.2026.1080p.BluRay.x264-SPARKS"


def test_title_falls_back_to_title_field(monkeypatch):
    """Fall back to title field when no better source is available."""
    comet, logs = _import_comet(monkeypatch)
    comet.base_url = "http://localhost"
    comet.b64config = "test"

    stream = _make_stream(
        infoHash="c" * 40,
        title="[RD] Comet 720p",
        size="5000000000",
    )
    response = SimpleNamespace(streams=[stream])
    monkeypatch.setattr(comet, "get", lambda url: response)

    results = comet.scrape("tt1234567", "tt1234567")
    assert len(results) == 1
    assert results[0].title == "[RD] Comet 720p"


def test_title_strips_mkv_extension(monkeypatch):
    """File extension should be stripped from behaviorHints.filename."""
    comet, logs = _import_comet(monkeypatch)
    comet.base_url = "http://localhost"
    comet.b64config = "test"

    stream = _make_stream(
        infoHash="d" * 40,
        title="[RD] Comet 2160p",
        behaviorHints=SimpleNamespace(filename="Movie.2026.2160p.WEB.DL.HEVC.mkv"),
        size="10000000000",
    )
    response = SimpleNamespace(streams=[stream])
    monkeypatch.setattr(comet, "get", lambda url: response)

    results = comet.scrape("tt1234567", "tt1234567")
    assert len(results) == 1
    assert results[0].title == "Movie.2026.2160p.WEB.DL.HEVC"
    assert ".mkv" not in results[0].title


def test_instance_title_from_behavior_hints(monkeypatch):
    """create_instance() scrape extracts title from behaviorHints.filename."""
    comet, logs = _import_comet(monkeypatch)
    # Set active to include the instance name
    services_mod = sys.modules["scraper.services"]
    setattr(services_mod, "active", ["comet-selfhosted"])

    instance = comet.create_instance("comet-selfhosted")
    instance.base_url = "http://localhost"
    instance.b64config = "test"

    stream = _make_stream(
        infoHash="e" * 40,
        title="[RD] Comet 2160p",
        behaviorHints=SimpleNamespace(filename="Some.Movie.2026.2160p.REMUX.mkv"),
        size="50000000000",
    )
    response = SimpleNamespace(streams=[stream])
    monkeypatch.setattr(comet, "get", lambda url: response)

    results = instance.scrape("tt1234567", "tt1234567")
    assert len(results) == 1
    assert results[0].title == "Some.Movie.2026.2160p.REMUX"
    assert results[0].source == "[comet-selfhosted]"
