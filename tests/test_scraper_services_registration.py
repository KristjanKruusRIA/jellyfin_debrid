"""Tests for scraper service registration without Torrentio startup wiring."""

import builtins
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _make_scraper_stub(module_name: str, service_name: str) -> ModuleType:
    stub = ModuleType(module_name)
    setattr(stub, "name", service_name)
    setattr(stub, "setup", lambda cls, new=False: None)
    setattr(stub, "scrape", lambda query, altquery="(.*)": [])
    return stub


def _import_scraper_services(monkeypatch, *, block_torrentio: bool = False):
    """Load scraper.services directly with optional torrentio import blocking."""
    repo_root = Path(__file__).resolve().parents[1]
    services_init = repo_root / "scraper" / "services" / "__init__.py"

    # Ensure fresh import each time
    for mod_name in [
        "scraper",
        "scraper.services",
        "scraper.services.aiostreams",
        "scraper.services.comet",
        "scraper.services.torrentio",
        "ui",
        "ui.ui_print",
    ]:
        sys.modules.pop(mod_name, None)

    # Stub package container to avoid executing scraper/__init__.py side-effects.
    scraper_pkg = ModuleType("scraper")
    scraper_pkg.__path__ = [str(repo_root / "scraper")]
    monkeypatch.setitem(sys.modules, "scraper", scraper_pkg)

    # Stub supported scrapers using project test-isolation pattern
    monkeypatch.setitem(
        sys.modules,
        "scraper.services.aiostreams",
        _make_scraper_stub("scraper.services.aiostreams", "aiostreams"),
    )
    monkeypatch.setitem(
        sys.modules,
        "scraper.services.comet",
        _make_scraper_stub("scraper.services.comet", "comet"),
    )

    # Stub ui logging module to avoid importing full ui package graph.
    ui_pkg = ModuleType("ui")
    ui_pkg.__path__ = []
    ui_print_stub = ModuleType("ui.ui_print")
    setattr(ui_print_stub, "ui_print", lambda *a, **k: None)
    setattr(ui_print_stub, "ui_settings", SimpleNamespace(debug="true", log="false"))
    setattr(ui_pkg, "ui_print", ui_print_stub)
    monkeypatch.setitem(sys.modules, "ui", ui_pkg)
    monkeypatch.setitem(sys.modules, "ui.ui_print", ui_print_stub)

    if block_torrentio:
        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            # Block both direct and fromlist-based torrentio imports.
            if name == "scraper.services.torrentio" or (
                name == "scraper.services" and "torrentio" in (fromlist or ())
            ):
                raise ImportError("torrentio intentionally unavailable in test")
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", guarded_import)

    spec = importlib.util.spec_from_file_location("scraper.services", services_init)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "scraper.services", module)
    setattr(scraper_pkg, "services", module)
    spec.loader.exec_module(module)

    return module


def test_import_scraper_services_succeeds_without_torrentio(monkeypatch):
    """Import should succeed even if torrentio is unavailable."""
    services = _import_scraper_services(monkeypatch, block_torrentio=True)
    assert services is not None


def test_active_default_excludes_torrentio(monkeypatch):
    services = _import_scraper_services(monkeypatch, block_torrentio=True)
    assert "torrentio" not in services.active_default


def test_subclasses_excludes_torrentio(monkeypatch):
    services = _import_scraper_services(monkeypatch, block_torrentio=True)
    names = [getattr(module, "name", "") for module in services.__subclasses__()]
    assert "torrentio" not in names


def test_get_returns_only_supported_scrapers(monkeypatch):
    services = _import_scraper_services(monkeypatch, block_torrentio=True)

    # Include unsupported names in active list; get() should only resolve registered services.
    setattr(services, "active", ["aiostreams", "comet", "torrentio", "does-not-exist"])
    resolved = services.get()
    resolved_names = [module.name for module in resolved]

    assert "aiostreams" in resolved_names
    assert "comet" in resolved_names
    assert "torrentio" not in resolved_names
    assert "does-not-exist" not in resolved_names
