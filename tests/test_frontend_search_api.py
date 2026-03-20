import sys
from types import ModuleType

import pytest

from frontend import app


def _stub_tmdb(monkeypatch, search_impl):
    tmdb_stub = ModuleType("content.services.tmdb")
    setattr(tmdb_stub, "search", search_impl)

    services_stub = ModuleType("content.services")
    setattr(services_stub, "tmdb", tmdb_stub)

    monkeypatch.setitem(sys.modules, "content.services", services_stub)
    monkeypatch.setitem(sys.modules, "content.services.tmdb", tmdb_stub)


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_search_api_returns_400_when_no_query(client):
    response = client.get("/api/search")

    assert response.status_code == 400
    payload = response.get_json()
    assert payload == {
        "query": "",
        "results": [],
        "count": 0,
        "error": "Missing required parameter: q",
    }


def test_search_api_returns_normalized_tmdb_results(client, monkeypatch):
    expected_results = [
        {
            "id": 1,
            "title": "Test Movie",
            "year": "2025",
            "media_type": "movie",
            "poster_path": "/poster.jpg",
            "overview": "Overview",
        },
        {
            "id": 2,
            "title": "Test Show",
            "year": "2024",
            "media_type": "tv",
            "poster_path": None,
            "overview": "Another overview",
        },
    ]

    def _search(query, media_type=None):
        assert query == "test"
        assert media_type is None
        return {"results": expected_results, "error": None}

    _stub_tmdb(monkeypatch, _search)

    response = client.get("/api/search?q=test")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "query": "test",
        "results": expected_results,
        "count": 2,
        "error": None,
    }


def test_search_api_supports_type_filter_movie_and_tv(client, monkeypatch):
    calls = []

    def _search(_query, media_type=None):
        calls.append(media_type)
        return {"results": [], "error": None}

    _stub_tmdb(monkeypatch, _search)

    movie_response = client.get("/api/search?q=test&type=movie")
    tv_response = client.get("/api/search?q=test&type=tv")

    assert movie_response.status_code == 200
    assert tv_response.status_code == 200
    assert calls == ["movie", "tv"]


def test_search_api_normalizes_type_all_and_invalid(client, monkeypatch):
    calls = []

    def _search(_query, media_type=None):
        calls.append(media_type)
        return {"results": [], "error": None}

    _stub_tmdb(monkeypatch, _search)

    client.get("/api/search?q=test&type=all")
    client.get("/api/search?q=test&type=bogus")
    client.get("/api/search?q=test")

    assert calls == [None, None, None]


def test_search_api_returns_error_payload_when_tmdb_unavailable(client, monkeypatch):
    def _search(_query, media_type=None):
        return {"results": [], "error": "TMDB API Key not configured"}

    _stub_tmdb(monkeypatch, _search)

    response = client.get("/api/search?q=test")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "query": "test",
        "results": [],
        "count": 0,
        "error": "TMDB API Key not configured",
    }


def test_search_api_never_exposes_traceback(client, monkeypatch):
    def _search(_query, media_type=None):
        raise RuntimeError("boom")

    _stub_tmdb(monkeypatch, _search)

    response = client.get("/api/search?q=test")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "query": "test",
        "results": [],
        "count": 0,
        "error": "Search service unavailable",
    }
    assert "Traceback" not in response.get_data(as_text=True)
