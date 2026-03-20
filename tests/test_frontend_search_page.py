import pytest

from frontend import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_search_page_renders_successfully(client):
    response = client.get("/search")
    assert response.status_code == 200


def test_search_page_contains_search_form(client):
    response = client.get("/search")
    html = response.data.decode("utf-8")
    assert "<input" in html
    assert (
        "type" in html
    )  # Check for type selector (like select optionally or something)
    assert "movie" in html.lower()


def test_search_page_links_to_or_coexists_with_logs_page(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "/search" in html
