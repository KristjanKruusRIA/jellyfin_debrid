"""Ensure settings metadata and template no longer reference Torrentio."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _import_settings_with_stubs(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    settings_init = repo_root / "settings" / "__init__.py"

    sys.modules.pop("settings", None)

    content_stub = ModuleType("content")
    setattr(
        content_stub,
        "services",
        SimpleNamespace(
            active=[],
            jellyseerr=SimpleNamespace(users=[], api_key="", base_url=""),
            jellyfin=SimpleNamespace(api_key="", library=SimpleNamespace(url="")),
        ),
    )
    setattr(
        content_stub,
        "classes",
        SimpleNamespace(
            library=SimpleNamespace(active=[]),
            refresh=SimpleNamespace(active=[]),
            ignore=SimpleNamespace(active=[]),
        ),
    )

    debrid_stub = ModuleType("debrid")
    setattr(
        debrid_stub,
        "services",
        SimpleNamespace(
            active=[],
            realdebrid=SimpleNamespace(
                api_key="",
                session=SimpleNamespace(
                    get=lambda url: SimpleNamespace(status_code=200)
                ),
            ),
        ),
    )

    releases_stub = ModuleType("releases")
    setattr(releases_stub, "sort", SimpleNamespace(versions=[]))
    setattr(releases_stub, "rename", SimpleNamespace(replaceChars=[]))

    scraper_stub = ModuleType("scraper")
    setattr(
        scraper_stub,
        "services",
        SimpleNamespace(
            active=[],
            aiostreams=SimpleNamespace(uuid="", b64config="", name="aiostreams"),
            comet=SimpleNamespace(base_url="", b64config="", name="comet"),
            comet_selfhosted=SimpleNamespace(
                base_url="", b64config="", name="comet-selfhosted"
            ),
            comet_elfhosted=SimpleNamespace(
                base_url="", b64config="", name="comet-elfhosted"
            ),
            comet_base=SimpleNamespace(base_url="", b64config="", name="comet-base"),
        ),
    )

    ui_package_stub = ModuleType("ui")
    ui_settings_stub = ModuleType("ui.ui_settings")
    setattr(ui_settings_stub, "run_directly", "true")
    setattr(ui_settings_stub, "debug", "false")
    setattr(ui_settings_stub, "log", "true")
    setattr(ui_settings_stub, "version", ["test", "", []])
    setattr(ui_package_stub, "ui_settings", ui_settings_stub)

    monkeypatch.setitem(sys.modules, "content", content_stub)
    monkeypatch.setitem(sys.modules, "debrid", debrid_stub)
    monkeypatch.setitem(sys.modules, "releases", releases_stub)
    monkeypatch.setitem(sys.modules, "scraper", scraper_stub)
    monkeypatch.setitem(sys.modules, "ui", ui_package_stub)
    monkeypatch.setitem(sys.modules, "ui.ui_settings", ui_settings_stub)

    spec = importlib.util.spec_from_file_location("settings", settings_init)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "settings", module)
    spec.loader.exec_module(module)

    return module


def test_settings_registry_contains_no_torrentio_setting_names(monkeypatch):
    settings_module = _import_settings_with_stubs(monkeypatch)

    names = [
        setting.name.lower()
        for _, section_settings in settings_module.settings_list
        for setting in section_settings
    ]

    assert all("torrentio" not in name for name in names)


def test_settings_template_contains_no_torrentio_text():
    repo_root = Path(__file__).resolve().parents[1]
    template_text = (repo_root / "settings.json.template").read_text(encoding="utf-8")

    assert "torrentio" not in template_text.lower()
