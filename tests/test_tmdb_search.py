"""Tests for TMDB search helper module."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlparse


def _make_response(payload, status_code=200):
    return SimpleNamespace(
        json=lambda: payload,
        status_code=status_code,
        raise_for_status=lambda: None,
    )


def _import_tmdb(monkeypatch, *, responder=None):
    """Load content.services.tmdb in isolation with stubbed dependencies."""
    repo_root = Path(__file__).resolve().parents[1]
    tmdb_path = repo_root / "content" / "services" / "tmdb.py"

    for mod_name in ["content.services.tmdb", "ui", "ui.ui_print", "requests"]:
        sys.modules.pop(mod_name, None)

    # Stub ui.ui_print
    logs = []
    ui_pkg = ModuleType("ui")
    ui_pkg.__path__ = []
    ui_print_mod = ModuleType("ui.ui_print")
    ui_settings_stub = SimpleNamespace(debug=True)

    def ui_print_fn(*args, **kwargs):
        logs.append((args, kwargs))

    setattr(ui_print_mod, "ui_print", ui_print_fn)
    setattr(ui_print_mod, "ui_settings", ui_settings_stub)
    setattr(ui_pkg, "ui_print", ui_print_mod)
    setattr(ui_pkg, "ui_settings", ui_settings_stub)
    monkeypatch.setitem(sys.modules, "ui", ui_pkg)
    monkeypatch.setitem(sys.modules, "ui.ui_print", ui_print_mod)

    # Stub requests.Session
    requests_mod = ModuleType("requests")

    class _DummySession:
        def __init__(self):
            self.calls = []

        def get(self, url, timeout=10):
            self.calls.append({"url": url, "timeout": timeout})
            if responder is None:
                return _make_response({"results": []})
            return responder(url, timeout)

    setattr(requests_mod, "Session", _DummySession)
    monkeypatch.setitem(sys.modules, "requests", requests_mod)

    spec = importlib.util.spec_from_file_location("content.services.tmdb", tmdb_path)
    assert spec is not None
    assert spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "content.services.tmdb", module)
    spec.loader.exec_module(module)
    return module, logs


def test_tmdb_search_calls_correct_endpoint(monkeypatch):
    tmdb, _ = _import_tmdb(monkeypatch)
    tmdb.api_key = "abc123"

    result = tmdb.search("The Office")

    assert result["error"] is None
    assert len(tmdb.session.calls) == 1

    called_url = tmdb.session.calls[0]["url"]
    parsed = urlparse(called_url)
    query = parse_qs(parsed.query)

    assert parsed.netloc == "api.themoviedb.org"
    assert parsed.path == "/3/search/multi"
    assert query["api_key"] == ["abc123"]
    assert query["query"] == ["The Office"]


def test_tmdb_search_normalizes_movie_and_tv_results(monkeypatch):
    payload = {
        "results": [
            {
                "id": 11,
                "media_type": "movie",
                "title": "Interstellar",
                "release_date": "2014-11-07",
                "poster_path": "/movie.jpg",
                "overview": "Space and time.",
            },
            {
                "id": 22,
                "media_type": "tv",
                "name": "Dark",
                "first_air_date": "2017-12-01",
                "poster_path": None,
                "overview": "Time travel mystery.",
            },
        ]
    }

    tmdb, _ = _import_tmdb(
        monkeypatch,
        responder=lambda _url, _timeout: _make_response(payload),
    )
    tmdb.api_key = "abc123"

    result = tmdb.search("whatever")

    assert result["error"] is None
    assert result["results"] == [
        {
            "id": 11,
            "title": "Interstellar",
            "year": "2014",
            "media_type": "movie",
            "poster_path": "/movie.jpg",
            "overview": "Space and time.",
        },
        {
            "id": 22,
            "title": "Dark",
            "year": "2017",
            "media_type": "tv",
            "poster_path": None,
            "overview": "Time travel mystery.",
        },
    ]


def test_tmdb_search_filters_people_results(monkeypatch):
    payload = {
        "results": [
            {
                "id": 100,
                "media_type": "person",
                "name": "Someone Famous",
                "overview": "",
            },
            {
                "id": 200,
                "media_type": "movie",
                "title": "A Movie",
                "release_date": "2020-01-01",
                "overview": "Overview",
                "poster_path": "/movie.png",
            },
        ]
    }

    tmdb, _ = _import_tmdb(
        monkeypatch,
        responder=lambda _url, _timeout: _make_response(payload),
    )
    tmdb.api_key = "abc123"

    result = tmdb.search("query")

    assert result["error"] is None
    assert len(result["results"]) == 1
    assert result["results"][0]["id"] == 200
    assert result["results"][0]["media_type"] == "movie"


def test_tmdb_search_handles_missing_api_key(monkeypatch):
    tmdb, _ = _import_tmdb(monkeypatch)
    tmdb.api_key = ""

    result = tmdb.search("query")

    assert result == {"results": [], "error": "TMDB API Key not configured"}


def test_tmdb_search_handles_empty_and_failed_responses(monkeypatch):
    tmdb_empty, _ = _import_tmdb(
        monkeypatch,
        responder=lambda _url, _timeout: _make_response({}),
    )
    tmdb_empty.api_key = "abc123"

    empty_result = tmdb_empty.search("query")

    assert empty_result == {"results": [], "error": None}

    def failing_responder(_url, _timeout):
        raise RuntimeError("network is down")

    tmdb_fail, _ = _import_tmdb(monkeypatch, responder=failing_responder)
    tmdb_fail.api_key = "abc123"

    failed_result = tmdb_fail.search("query")

    assert failed_result["results"] == []
    assert failed_result["error"] == "TMDB search failed: network is down"


def test_tmdb_search_handles_http_error_status(monkeypatch):
    """Verify non-2xx HTTP responses are treated as failures."""

    def error_responder(_url, _timeout):
        resp = SimpleNamespace(
            status_code=401,
            json=lambda: {"status_message": "Invalid API key"},
        )

        def raise_for_status():
            raise Exception("401 Client Error: Unauthorized")

        resp.raise_for_status = raise_for_status
        return resp

    tmdb, _ = _import_tmdb(monkeypatch, responder=error_responder)
    tmdb.api_key = "abc123"

    result = tmdb.search("query")

    assert result["results"] == []
    assert result["error"] is not None
    assert "401" in result["error"]
