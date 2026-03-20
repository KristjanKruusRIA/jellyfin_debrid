import importlib.util
import sys
import uuid
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _module(name: str, **attrs):
    mod = ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def _import_frontend(
    monkeypatch,
    *,
    tmdb_module=None,
    manual_media_module=None,
    scraper_module=None,
    debrid_module=None,
):
    repo_root = Path(__file__).resolve().parents[1]
    frontend_path = repo_root / "frontend.py"

    ui_print_mod = _module(
        "ui.ui_print",
        ui_print=lambda *_args, **_kwargs: None,
        ui_settings=SimpleNamespace(debug=False),
    )
    ui_mod = _module("ui", ui_print=ui_print_mod)

    monkeypatch.setitem(sys.modules, "ui", ui_mod)
    monkeypatch.setitem(sys.modules, "ui.ui_print", ui_print_mod)

    class _FakeMedia:
        Releases: list

        def __init__(self, query_text: str = "fake.media"):
            self.Releases = []
            self._query_text = query_text

        def query(self):
            return self._query_text

        def deviation(self):
            return "(.*)"

    if tmdb_module is None:
        tmdb_module = _module(
            "content.services.tmdb",
            search=lambda *_args, **_kwargs: {"results": [], "error": None},
            get_movie_details=lambda tmdb_id: {"id": int(tmdb_id), "title": "Movie"},
            get_show_details=lambda tmdb_id: {"id": int(tmdb_id), "title": "Show"},
        )

    if manual_media_module is None:
        manual_media_module = _module(
            "content.services.manual_media",
            build_movie=lambda _details: _FakeMedia("movie.query"),
            build_show=lambda _details: _FakeMedia("show.query"),
        )

    if scraper_module is None:
        scraper_module = _module("scraper", scrape=lambda *_args, **_kwargs: [])

    if debrid_module is None:
        debrid_module = _module(
            "debrid",
            check=lambda *_args, **_kwargs: None,
            download=lambda *_args, **_kwargs: None,
        )

    services_mod = _module(
        "content.services",
        tmdb=tmdb_module,
        manual_media=manual_media_module,
    )

    monkeypatch.setitem(sys.modules, "content.services", services_mod)
    monkeypatch.setitem(sys.modules, "content.services.tmdb", tmdb_module)
    monkeypatch.setitem(
        sys.modules, "content.services.manual_media", manual_media_module
    )
    monkeypatch.setitem(sys.modules, "scraper", scraper_module)
    monkeypatch.setitem(sys.modules, "debrid", debrid_module)

    module_name = f"frontend_test_download_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, str(frontend_path))
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_download_endpoint_can_report_cached_vs_uncached_choice(monkeypatch):
    class _FakeMedia:
        def __init__(self):
            self.Releases = []

        def query(self):
            return "fight.club.1999"

        def deviation(self):
            return "(.*)"

    tmdb_mod = _module(
        "content.services.tmdb",
        search=lambda *_args, **_kwargs: {"results": [], "error": None},
        get_movie_details=lambda _tmdb_id: {"id": 550, "title": "Fight Club"},
        get_show_details=lambda _tmdb_id: {"id": 1, "title": "Show"},
    )
    manual_media_mod = _module(
        "content.services.manual_media",
        build_movie=lambda _details: _FakeMedia(),
        build_show=lambda _details: _FakeMedia(),
    )

    frontend = _import_frontend(
        monkeypatch,
        tmdb_module=tmdb_mod,
        manual_media_module=manual_media_mod,
    )
    frontend.app.config.update(TESTING=True)

    cached_release = SimpleNamespace(
        title="Cached Release",
        source="[aiostreams]",
        type="magnet",
        size=10.0,
        seeders=10,
        resolution="1080",
        cached=["realdebrid"],
        files=[{"id": 1}],
        wanted=1,
        unwanted=0,
        download=["magnet:?xt=urn:btih:cached"],
        hash="cachedhash",
    )

    uncached_release = SimpleNamespace(
        title="Uncached Release",
        source="[comet]",
        type="magnet",
        size=8.0,
        seeders=5,
        resolution="720",
        cached=[],
        files=[{"id": 1}],
        wanted=1,
        unwanted=0,
        download=["magnet:?xt=urn:btih:uncached"],
        hash="uncachedhash",
    )

    job_id = frontend.registry.create_job(550, "movie", "Fight Club")
    frontend.registry.update_job(
        job_id, "complete", releases=[cached_release, uncached_release]
    )

    with frontend.app.test_client() as client:
        cached_response = client.post(
            f"/api/scrapes/{job_id}/downloads", json={"release_id": "0"}
        )
        uncached_response = client.post(
            f"/api/scrapes/{job_id}/downloads", json={"release_id": "1"}
        )

    assert cached_response.status_code == 200
    cached_payload = cached_response.get_json()
    assert cached_payload["status"] == "started"
    assert cached_payload["cached"] is True
    assert cached_payload["cached_via"] == ["realdebrid"]

    assert uncached_response.status_code == 200
    uncached_payload = uncached_response.get_json()
    assert uncached_payload["status"] == "started"
    assert uncached_payload["cached"] is False
    assert uncached_payload["cached_via"] == []
