import pytest

from frontend import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_root_logs_page_still_works(client):
    response = client.get("/")
    assert response.status_code == 200

    html = response.data.decode("utf-8")
    assert "Jellyfin Debrid Logs" in html or 'id="logs"' in html


def test_logs_api_still_works_after_search_routes_added(client):
    response = client.get("/api/logs")
    assert response.status_code == 200

    data = response.get_json()
    assert isinstance(data, dict)
    assert "content" in data
