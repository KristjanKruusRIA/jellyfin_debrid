"""Tests for Comet multi-instance factory and scraper registration."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


class _DummySession:
    def __init__(self):
        self.headers = {}

    def get(self, url, timeout=60):
        raise RuntimeError("network disabled in unit tests")


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _import_comet(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    comet_path = repo_root / "scraper" / "services" / "comet.py"

    for mod_name in [
        "scraper.services.comet",
        "ui",
        "ui.ui_print",
        "releases",
        "base",
    ]:
        sys.modules.pop(mod_name, None)

    ui_pkg = ModuleType("ui")
    ui_pkg.__path__ = []
    ui_print_mod = ModuleType("ui.ui_print")
    setattr(ui_print_mod, "ui_print", lambda *a, **k: None)
    setattr(ui_print_mod, "ui_settings", SimpleNamespace(debug="true", log="false"))
    setattr(ui_pkg, "ui_print", ui_print_mod)
    monkeypatch.setitem(sys.modules, "ui", ui_pkg)
    monkeypatch.setitem(sys.modules, "ui.ui_print", ui_print_mod)

    releases_mod = ModuleType("releases")
    setattr(releases_mod, "release", object)
    monkeypatch.setitem(sys.modules, "releases", releases_mod)

    import copy
    import json
    import time

    base_mod = ModuleType("base")
    setattr(base_mod, "SimpleNamespace", SimpleNamespace)
    setattr(base_mod, "copy", copy)
    setattr(base_mod, "custom_session", _DummySession)
    setattr(base_mod, "json", json)
    setattr(base_mod, "regex", object())
    setattr(base_mod, "time", time)
    monkeypatch.setitem(sys.modules, "base", base_mod)

    return _load_module("scraper.services.comet", comet_path)


def _make_scraper_stub(module_name: str, service_name: str) -> ModuleType:
    stub = ModuleType(module_name)
    setattr(stub, "name", service_name)
    setattr(stub, "setup", lambda cls, new=False: None)
    setattr(stub, "scrape", lambda query, altquery="(.*)": [])
    return stub


def _import_scraper_services(monkeypatch):
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

    comet_stub = ModuleType("scraper.services.comet")
    setattr(comet_stub, "name", "comet")

    def create_instance(instance_name):
        instance = SimpleNamespace(
            name=instance_name,
            base_url="",
            b64config="",
        )
        instance.scrape = lambda query, altquery="(.*)": []
        instance.setup = lambda cls, new=False: None
        return instance

    setattr(comet_stub, "create_instance", create_instance)
    monkeypatch.setitem(sys.modules, "scraper.services.comet", comet_stub)

    ui_pkg = ModuleType("ui")
    ui_pkg.__path__ = []
    ui_print_stub = ModuleType("ui.ui_print")
    setattr(ui_print_stub, "ui_print", lambda *a, **k: None)
    setattr(ui_print_stub, "ui_settings", SimpleNamespace(debug="true", log="false"))
    setattr(ui_pkg, "ui_print", ui_print_stub)
    monkeypatch.setitem(sys.modules, "ui", ui_pkg)
    monkeypatch.setitem(sys.modules, "ui.ui_print", ui_print_stub)

    spec = importlib.util.spec_from_file_location("scraper.services", services_init)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "scraper.services", module)
    setattr(scraper_pkg, "services", module)
    spec.loader.exec_module(module)

    return module


def test_factory_creates_distinct_instances(monkeypatch):
    comet = _import_comet(monkeypatch)

    instance_a = comet.create_instance("a")
    instance_b = comet.create_instance("b")

    assert instance_a.name == "a"
    assert instance_b.name == "b"
    assert instance_a is not instance_b

    instance_a.base_url = "http://a"
    instance_a.b64config = "cfg-a"

    assert instance_b.base_url == ""
    assert instance_b.b64config == ""


def test_instance_uses_own_config(monkeypatch):
    comet = _import_comet(monkeypatch)

    primary = comet.create_instance("comet-selfhosted")
    secondary = comet.create_instance("comet-base")

    primary.base_url = "https://example.local"
    primary.b64config = "encoded-config"

    assert primary.base_url == "https://example.local"
    assert primary.b64config == "encoded-config"
    assert secondary.base_url == ""
    assert secondary.b64config == ""


def test_three_comet_instances_registered(monkeypatch):
    services = _import_scraper_services(monkeypatch)

    comet_like_names = [
        service.name
        for service in services.scrapers
        if service.name.startswith("comet-")
    ]

    assert comet_like_names == [
        "comet-selfhosted",
        "comet-elfhosted",
        "comet-base",
    ]

    assert hasattr(services, "comet_selfhosted")
    assert hasattr(services, "comet_elfhosted")
    assert hasattr(services, "comet_base")
