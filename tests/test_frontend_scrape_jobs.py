import time
from types import SimpleNamespace

from frontend_jobs import JobRegistry


def _make_release(title: str) -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        source="[source]",
        type="magnet",
        size=1.0,
        seeders=1,
        resolution="1080",
        cached=[],
        files=[],
        wanted=0,
        unwanted=0,
        download=["magnet:?xt=urn:btih:abc&dn=test"],
        hash="abc",
    )


def test_create_scrape_job_returns_opaque_job_id():
    registry = JobRegistry()

    first_job_id = registry.create_job(
        tmdb_id=550,
        media_type="movie",
        media_title="Fight Club",
    )
    second_job_id = registry.create_job(
        tmdb_id=551,
        media_type="movie",
        media_title="The Matrix",
    )

    assert isinstance(first_job_id, str)
    assert isinstance(second_job_id, str)
    assert len(first_job_id) == 32
    assert len(second_job_id) == 32
    assert first_job_id != second_job_id
    assert registry.get_job(first_job_id) is not None


def test_create_scrape_job_with_season_number():
    registry = JobRegistry()

    job_id = registry.create_job(
        tmdb_id=1399,
        media_type="tv",
        media_title="Game of Thrones",
        season_number=2,
    )

    job = registry.get_job(job_id)
    assert job is not None
    assert job.season_number == 2


def test_scrape_job_tracks_running_complete_and_failed_states():
    registry = JobRegistry()
    job_id = registry.create_job(1, "show", "Some Show")

    registry.update_job(job_id, status="running")
    running_job = registry.get_job(job_id)
    assert running_job is not None
    assert running_job.status == "running"

    releases = [_make_release("Release 1"), _make_release("Release 2")]
    registry.update_job(job_id, status="complete", releases=releases)

    complete_job = registry.get_job(job_id)
    assert complete_job is not None
    assert complete_job.status == "complete"
    assert complete_job.releases == releases

    failed_job_id = registry.create_job(2, "movie", "Broken Movie")
    registry.update_job(failed_job_id, status="failed", error="scrape failed")
    failed_job = registry.get_job(failed_job_id)

    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.error == "scrape failed"


def test_job_registry_rejects_unknown_or_expired_job_ids():
    registry = JobRegistry()

    assert registry.get_job("missing") is None
    assert registry.get_release("missing", "0") is None

    job_id = registry.create_job(99, "movie", "Old Job")
    job = registry.get_job(job_id)
    assert job is not None
    job.created_at = time.time() - 7201

    registry.cleanup(max_age_seconds=3600)

    assert registry.get_job(job_id) is None
    assert registry.get_release(job_id, "0") is None
