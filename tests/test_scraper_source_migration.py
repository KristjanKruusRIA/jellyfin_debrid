"""Tests for runtime source migration guardrails in scraper.services."""

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


def _import_scraper_services(monkeypatch):
    """Load scraper.services in isolation with stubbed dependencies."""
    repo_root = Path(__file__).resolve().parents[1]
    services_init = repo_root / "scraper" / "services" / "__init__.py"

    for mod_name in [
        "scraper",
        "scraper.services",
        "scraper.services.aiostreams",
        "scraper.services.comet",
        "ui",
        "ui.ui_print",
    ]:
        sys.modules.pop(mod_name, None)

    scraper_pkg = ModuleType("scraper")
    scraper_pkg.__path__ = [str(repo_root / "scraper")]
    monkeypatch.setitem(sys.modules, "scraper", scraper_pkg)

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

    logs = []

    ui_pkg = ModuleType("ui")
    ui_pkg.__path__ = []
    ui_print_stub = ModuleType("ui.ui_print")
    ui_settings_stub = SimpleNamespace(debug="true", log="false")

    def ui_print_fn(*args, **kwargs):
        logs.append((args, kwargs))

    setattr(ui_print_stub, "ui_print", ui_print_fn)
    setattr(ui_print_stub, "ui_settings", ui_settings_stub)

    setattr(ui_pkg, "ui_print", ui_print_stub)
    setattr(ui_pkg, "ui_settings", ui_settings_stub)
    monkeypatch.setitem(sys.modules, "ui", ui_pkg)
    monkeypatch.setitem(sys.modules, "ui.ui_print", ui_print_stub)

    spec = importlib.util.spec_from_file_location("scraper.services", services_init)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "scraper.services", module)
    setattr(scraper_pkg, "services", module)
    spec.loader.exec_module(module)

    return module, logs


def _log_messages(logs):
    return [entry[0][0] for entry in logs if entry and entry[0]]


def test_get_warns_on_unsupported_source(monkeypatch):
    services, logs = _import_scraper_services(monkeypatch)

    aiostreams_module = SimpleNamespace(name="aiostreams")
    comet_module = SimpleNamespace(name="comet")
    monkeypatch.setattr(
        services, "__subclasses__", lambda: [aiostreams_module, comet_module]
    )
    setattr(services, "active", ["torrentio", "aiostreams"])

    resolved = services.get()

    assert resolved == [aiostreams_module]

    messages = _log_messages(logs)
    assert any(
        "warning: ignoring unsupported source 'torrentio'" in msg for msg in messages
    )


def test_get_errors_on_all_unsupported(monkeypatch):
    services, logs = _import_scraper_services(monkeypatch)

    aiostreams_module = SimpleNamespace(name="aiostreams")
    comet_module = SimpleNamespace(name="comet")
    monkeypatch.setattr(
        services, "__subclasses__", lambda: [aiostreams_module, comet_module]
    )
    setattr(services, "active", ["torrentio"])

    resolved = services.get()

    assert resolved == []

    messages = _log_messages(logs)
    assert any(
        "warning: ignoring unsupported source 'torrentio'" in msg for msg in messages
    )
    assert any(
        "error: no supported sources found in Sources config" in msg for msg in messages
    )


def test_get_works_with_valid_sources_only(monkeypatch):
    services, logs = _import_scraper_services(monkeypatch)

    aiostreams_module = SimpleNamespace(name="aiostreams")
    comet_module = SimpleNamespace(name="comet")
    monkeypatch.setattr(
        services, "__subclasses__", lambda: [aiostreams_module, comet_module]
    )
    setattr(services, "active", ["aiostreams", "comet"])

    resolved = services.get()

    assert resolved == [aiostreams_module, comet_module]

    messages = _log_messages(logs)
    assert not any("[scraper] warning" in msg for msg in messages)
    assert not any("[scraper] error" in msg for msg in messages)


def test_sequential_warns_on_unsupported_source(monkeypatch):
    services, logs = _import_scraper_services(monkeypatch)

    aiostreams_module = SimpleNamespace(name="aiostreams")
    comet_module = SimpleNamespace(name="comet")
    monkeypatch.setattr(
        services, "__subclasses__", lambda: [aiostreams_module, comet_module]
    )
    setattr(services, "overwrite", [["torrentio", "aiostreams"]])

    resolved = services.sequential()

    assert resolved == [[aiostreams_module]]

    messages = _log_messages(logs)
    assert any(
        "warning: ignoring unsupported source 'torrentio'" in msg for msg in messages
    )
