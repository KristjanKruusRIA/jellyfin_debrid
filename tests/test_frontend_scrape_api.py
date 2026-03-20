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


def test_create_scrape_request_validates_tmdb_id_and_media_type(monkeypatch):
    frontend = _import_frontend(monkeypatch)
    frontend.app.config.update(TESTING=True)

    with frontend.app.test_client() as client:
        missing_tmdb = client.post("/api/scrapes", json={"media_type": "movie"})
        invalid_type = client.post(
            "/api/scrapes", json={"tmdb_id": 550, "media_type": "anime"}
        )

    assert missing_tmdb.status_code == 400
    assert missing_tmdb.get_json()["status"] == "error"

    assert invalid_type.status_code == 400
    assert invalid_type.get_json()["status"] == "error"


def test_create_scrape_request_returns_job_id_and_accepted_state(monkeypatch):
    class _NoopThread:
        def __init__(self, target=None, args=(), daemon=False):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            return None

    frontend = _import_frontend(monkeypatch, thread_cls=_NoopThread)
    frontend.app.config.update(TESTING=True)

    with frontend.app.test_client() as client:
        response = client.post(
            "/api/scrapes",
            json={"tmdb_id": 550, "media_type": "movie", "title": "Fight Club"},
        )

    assert response.status_code == 202
    payload = response.get_json()
    assert payload["status"] == "running"
    assert isinstance(payload["job_id"], str)
    assert len(payload["job_id"]) > 0
    assert payload["error"] is None


def test_tmdb_lookup_movie_returns_normalized_result(monkeypatch):
    tmdb_mod = _module(
        "content.services.tmdb",
        search=lambda *_args, **_kwargs: {"results": [], "error": None},
        get_movie_details=lambda _tmdb_id: {
            "id": 603,
            "title": "The Matrix",
            "year": "1999",
            "release_date": "1999-03-30",
            "imdb_id": "tt0133093",
            "external_ids": {"imdb_id": "tt0133093"},
            "poster_path": "/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg",
            "overview": "A computer hacker learns about the true nature of reality.",
        },
        get_show_details=lambda _tmdb_id: {},
    )

    frontend = _import_frontend(monkeypatch, tmdb_module=tmdb_mod)
    frontend.app.config.update(TESTING=True)

    with frontend.app.test_client() as client:
        response = client.get("/api/tmdb/movie/603")

    assert response.status_code == 200
    assert response.get_json() == {
        "id": 603,
        "title": "The Matrix",
        "year": "1999",
        "media_type": "movie",
        "poster_path": "/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg",
        "overview": "A computer hacker learns about the true nature of reality.",
    }


def test_tmdb_lookup_tv_returns_normalized_result(monkeypatch):
    tmdb_mod = _module(
        "content.services.tmdb",
        search=lambda *_args, **_kwargs: {"results": [], "error": None},
        get_movie_details=lambda _tmdb_id: {},
        get_show_details=lambda _tmdb_id: {
            "id": 1399,
            "title": "Game of Thrones",
            "year": "2011",
            "first_air_date": "2011-04-17",
            "imdb_id": "tt0944947",
            "external_ids": {"imdb_id": "tt0944947"},
            "seasons": [{"season_number": 1}],
            "poster_path": "/1XS1oqL89opfnbLl8WnZY1O1uJx.jpg",
            "overview": "Seven noble families fight for control of Westeros.",
        },
    )

    frontend = _import_frontend(monkeypatch, tmdb_module=tmdb_mod)
    frontend.app.config.update(TESTING=True)

    with frontend.app.test_client() as client:
        response = client.get("/api/tmdb/tv/1399")

    assert response.status_code == 200
    assert response.get_json() == {
        "id": 1399,
        "title": "Game of Thrones",
        "year": "2011",
        "media_type": "tv",
        "poster_path": "/1XS1oqL89opfnbLl8WnZY1O1uJx.jpg",
        "overview": "Seven noble families fight for control of Westeros.",
    }


def test_tmdb_lookup_invalid_media_type_returns_400(monkeypatch):
    frontend = _import_frontend(monkeypatch)
    frontend.app.config.update(TESTING=True)

    with frontend.app.test_client() as client:
        response = client.get("/api/tmdb/invalid/603")

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"


def test_tmdb_lookup_invalid_tmdb_id_returns_400(monkeypatch):
    frontend = _import_frontend(monkeypatch)
    frontend.app.config.update(TESTING=True)

    with frontend.app.test_client() as client:
        response = client.get("/api/tmdb/movie/not-a-number")

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"


def test_tmdb_lookup_not_found_returns_404(monkeypatch):
    tmdb_mod = _module(
        "content.services.tmdb",
        search=lambda *_args, **_kwargs: {"results": [], "error": None},
        get_movie_details=lambda _tmdb_id: {},
        get_show_details=lambda _tmdb_id: {},
    )

    frontend = _import_frontend(monkeypatch, tmdb_module=tmdb_mod)
    frontend.app.config.update(TESTING=True)

    def test_search_page_loads_with_deep_link_params(monkeypatch):
        frontend = _import_frontend(monkeypatch)
        frontend.app.config.update(TESTING=True)

        with frontend.app.test_client() as client:
            response = client.get("/search?tmdb_id=603&media_type=movie")

        assert response.status_code == 200
        assert b"<!DOCTYPE html>" in response.data

    with frontend.app.test_client() as client:
        response = client.get("/api/tmdb/movie/99999999")

    assert response.status_code == 404
    payload = response.get_json()
    assert payload["status"] == "error"


def test_search_page_loads_with_deep_link_params(monkeypatch):
    frontend = _import_frontend(monkeypatch)
    frontend.app.config.update(TESTING=True)

    with frontend.app.test_client() as client:
        response = client.get("/search?tmdb_id=603&media_type=movie")

    assert response.status_code == 200
    assert b"<!DOCTYPE html>" in response.data


def test_scrape_status_endpoint_returns_release_summaries(monkeypatch):
    frontend = _import_frontend(monkeypatch)
    frontend.app.config.update(TESTING=True)

    release = SimpleNamespace(
        title="Fight Club 1999 1080p",
        source="[aiostreams]",
        type="magnet",
        size=12.5,
        seeders=20,
        resolution="1080",
        cached=["realdebrid"],
        files=[{"id": 1}, {"id": 2}],
        wanted=1,
        unwanted=0,
        download=["magnet:?xt=urn:btih:abc"],
        hash="abc",
    )

    job_id = frontend.registry.create_job(550, "movie", "Fight Club")
    frontend.registry.update_job(job_id, "complete", releases=[release])

    with frontend.app.test_client() as client:
        response = client.get(f"/api/scrapes/{job_id}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "complete"
    assert payload["count"] == 1
    assert payload["media"] == {"title": "Fight Club", "type": "movie", "tmdb_id": 550}
    assert payload["results"][0]["release_id"] == "0"
    assert "download" not in payload["results"][0]
    assert "hash" not in payload["results"][0]


def test_scrape_status_endpoint_returns_error_for_unknown_job(monkeypatch):
    frontend = _import_frontend(monkeypatch)
    frontend.app.config.update(TESTING=True)

    with frontend.app.test_client() as client:
        response = client.get("/api/scrapes/does-not-exist")

    assert response.status_code == 404
    payload = response.get_json()
    assert payload["status"] == "error"


def test_download_endpoint_requires_valid_job_and_release_id(monkeypatch):
    frontend = _import_frontend(monkeypatch)
    frontend.app.config.update(TESTING=True)

    job_id = frontend.registry.create_job(550, "movie", "Fight Club")

    with frontend.app.test_client() as client:
        missing_release = client.post(f"/api/scrapes/{job_id}/downloads", json={})
        unknown_job = client.post(
            "/api/scrapes/unknown/downloads", json={"release_id": "0"}
        )

    assert missing_release.status_code == 400
    assert missing_release.get_json()["status"] == "error"

    assert unknown_job.status_code == 404
    assert unknown_job.get_json()["status"] == "error"


def test_download_endpoint_calls_debrid_download_backend(monkeypatch):
    calls = []

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

    def _download(element, query="", force=False):
        calls.append(
            {
                "element": element,
                "query": query,
                "force": force,
            }
        )

    debrid_mod = _module(
        "debrid",
        check=lambda *_args, **_kwargs: None,
        download=_download,
    )

    frontend = _import_frontend(
        monkeypatch,
        tmdb_module=tmdb_mod,
        manual_media_module=manual_media_mod,
        debrid_module=debrid_mod,
    )
    frontend.app.config.update(TESTING=True)

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
        download=["magnet:?xt=urn:btih:abc"],
        hash="abc",
    )

    job_id = frontend.registry.create_job(550, "movie", "Fight Club")
    frontend.registry.update_job(job_id, "complete", releases=[release])

    with frontend.app.test_client() as client:
        response = client.post(
            f"/api/scrapes/{job_id}/downloads", json={"release_id": "0"}
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "started"
    assert payload["error"] is None

    assert len(calls) == 1
    assert calls[0]["force"] is True
    assert calls[0]["query"] == "fight.club.1999"
    assert len(calls[0]["element"].Releases) == 1
    assert calls[0]["element"].Releases[0] is release


def test_new_api_endpoints_never_expose_tracebacks(monkeypatch):
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
    debrid_mod = _module(
        "debrid",
        check=lambda *_args, **_kwargs: None,
        download=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    frontend = _import_frontend(
        monkeypatch,
        tmdb_module=tmdb_mod,
        manual_media_module=manual_media_mod,
        debrid_module=debrid_mod,
    )
    frontend.app.config.update(TESTING=True)

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
    assert "Traceback" not in response.get_data(as_text=True)


def test_failed_scrape_job_does_not_expose_internal_error(monkeypatch):
    frontend = _import_frontend(monkeypatch)
    frontend.app.config.update(TESTING=True)

    job_id = frontend.registry.create_job(550, "movie", "Fight Club")
    frontend.registry.update_job(job_id, "failed", error="Scrape failed")

    with frontend.app.test_client() as client:
        response = client.get(f"/api/scrapes/{job_id}")

    payload = response.get_json()
    assert payload["status"] == "failed"
    assert payload["error"] == "Scrape failed"
    assert "Exception" not in (payload["error"] or "")
    assert "Traceback" not in (payload["error"] or "")
