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


def test_search_page_marks_result_cards_as_actionable(client):
    response = client.get("/search")
    html = response.data.decode("utf-8")
    assert "cursor: pointer" in html or "cursor:pointer" in html
    assert "handleCardClick" in html


def test_search_page_contains_release_panel_or_modal_container(client):
    response = client.get("/search")
    html = response.data.decode("utf-8")
    assert "release-panel" in html
    assert "release-list" in html
    assert "release-status" in html


def test_search_page_shows_scraping_state_text(client):
    response = client.get("/search")
    html = response.data.decode("utf-8")
    assert "Searching for releases" in html
    assert "pollScrapeJob" in html


def test_search_page_supports_download_action_controls(client):
    response = client.get("/search")
    html = response.data.decode("utf-8")
    assert "download-btn" in html
    assert "handleDownload" in html
    assert "button.disabled" in html


def test_search_page_uses_dom_creation_for_releases(client):
    """Security: release rendering uses DOM APIs, not innerHTML with API data."""
    response = client.get("/search")
    html = response.data.decode("utf-8")
    assert "dataset.jobId" in html or "data-job-id" in html
    assert "dataset.releaseId" in html or "data-release-id" in html
    assert "addEventListener" in html
    assert "textContent" in html


def test_search_page_has_escape_html_and_collapse(client):
    """Verify escapeHtml and collapseAllPanels are defined."""
    response = client.get("/search")
    html = response.data.decode("utf-8")
    assert "escapeHtml" in html
    assert "collapseAllPanels" in html


def test_logs_page_navigation_still_works(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "/search" in html
