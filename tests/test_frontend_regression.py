import importlib.util
import sys
import uuid
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from frontend import app


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
    thread_cls=None,
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

    module_name = f"frontend_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, str(frontend_path))
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if thread_cls is not None:
        monkeypatch.setattr(module.threading, "Thread", thread_cls)

    return module


def _stub_tmdb_search(monkeypatch, search_impl):
    tmdb_stub = _module("content.services.tmdb", search=search_impl)
    services_stub = _module("content.services", tmdb=tmdb_stub)

    monkeypatch.setitem(sys.modules, "content.services", services_stub)
    monkeypatch.setitem(sys.modules, "content.services.tmdb", tmdb_stub)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_existing_search_api_still_returns_tmdb_results(client, monkeypatch):
    expected_results = [
        {
            "id": 1,
            "title": "Test Movie",
            "year": "2025",
            "media_type": "movie",
            "poster_path": "/poster.jpg",
            "overview": "Overview",
        }
    ]

    def _search(query, media_type=None):
        assert query == "test"
        assert media_type is None
        return {"results": expected_results, "error": None}

    _stub_tmdb_search(monkeypatch, _search)

    response = client.get("/api/search?q=test")

    assert response.status_code == 200
    assert response.get_json() == {
        "query": "test",
        "results": expected_results,
        "count": 1,
        "error": None,
    }


def test_logs_routes_still_work_after_scrape_download_additions(client):
    page_response = client.get("/")
    assert page_response.status_code == 200

    html = page_response.data.decode("utf-8")
    assert "Jellyfin Debrid Logs" in html or 'id="logs"' in html

    logs_response = client.get("/api/logs")
    assert logs_response.status_code == 200

    data = logs_response.get_json()
    assert isinstance(data, dict)
    assert "content" in data


def test_scrape_endpoints_do_not_require_seerr_configuration(monkeypatch):
    class _ImmediateThread:
        def __init__(self, target=None, args=(), daemon=False):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            if self.target is not None:
                self.target(*self.args)

    release = SimpleNamespace(
        title="Fight Club 1999 1080p",
        source="[aiostreams]",
        type="magnet",
        size=12.5,
        seeders=20,
        resolution="1080",
        cached=["realdebrid"],
        files=[{"id": 1}],
        wanted=1,
        unwanted=0,
    )

    scraper_mod = _module("scraper", scrape=lambda *_args, **_kwargs: [release])

    frontend = _import_frontend(
        monkeypatch,
        scraper_module=scraper_mod,
        thread_cls=_ImmediateThread,
    )
    frontend.app.config.update(TESTING=True)

    with frontend.app.test_client() as client:
        create_response = client.post(
            "/api/scrapes",
            json={"tmdb_id": 550, "media_type": "movie", "title": "Fight Club"},
        )
        assert create_response.status_code == 202
        job_id = create_response.get_json()["job_id"]

        status_response = client.get(f"/api/scrapes/{job_id}")

    assert status_response.status_code == 200
    payload = status_response.get_json()
    assert payload["status"] == "complete"
    assert payload["count"] == 1
    assert payload["error"] is None


def test_download_route_returns_structured_error_when_no_debrid_service_is_available(
    monkeypatch,
):
    debrid_mod = _module(
        "debrid",
        check=lambda *_args, **_kwargs: None,
        download=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("No debrid service configured")
        ),
    )

    frontend = _import_frontend(monkeypatch, debrid_module=debrid_mod)
    frontend.app.config.update(TESTING=True)

    release = SimpleNamespace(
        title="Fight Club 1999 1080p",
        source="[aiostreams]",
        type="magnet",
        size=12.5,
        seeders=20,
        resolution="1080",
        cached=[],
        files=[{"id": 1}],
        wanted=1,
        unwanted=0,
        download=["magnet:?xt=urn:btih:abc"],
        hash="abc",
    )

    job_id = frontend.registry.create_job(550, "movie", "Fight Club")
    frontend.registry.update_job(job_id, "complete", releases=[release])

    with frontend.app.test_client() as client:
        response = client.post(
            f"/api/scrapes/{job_id}/downloads", json={"release_id": "0"}
        )

    assert response.status_code == 500
    assert response.get_json() == {
        "status": "error",
        "error": "Download failed",
        "job_id": job_id,
    }
    assert "Traceback" not in response.get_data(as_text=True)
