from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ui.ui_print import ui_print, ui_settings


@dataclass
class ScrapeJob:
    job_id: str
    status: str
    media_type: str
    media_title: str
    tmdb_id: int
    releases: list[Any] = field(default_factory=list)
    error: str | None = None
    created_at: float = field(default_factory=time.time)


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, ScrapeJob] = {}

    def create_job(self, tmdb_id: int, media_type: str, media_title: str) -> str:
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = ScrapeJob(
            job_id=job_id,
            status="pending",
            media_type=media_type,
            media_title=media_title,
            tmdb_id=int(tmdb_id),
        )
        ui_print(
            f"[frontend_jobs] created scrape job {job_id}", debug=ui_settings.debug
        )
        return job_id

    def get_job(self, job_id: str) -> ScrapeJob | None:
        return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: str,
        releases: list[Any] | None = None,
        error: str | None = None,
    ) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            ui_print(
                f"[frontend_jobs] attempted to update unknown job {job_id}",
                debug=ui_settings.debug,
            )
            return

        job.status = status
        if releases is not None:
            job.releases = list(releases)
        job.error = error

        ui_print(
            f"[frontend_jobs] updated job {job_id} to status={status}",
            debug=ui_settings.debug,
        )

    def get_release(self, job_id: str, release_id: str) -> Any | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None

        try:
            index = int(release_id)
        except (TypeError, ValueError):
            return None

        if index < 0 or index >= len(job.releases):
            return None

        return job.releases[index]

    def cleanup(self, max_age_seconds: int = 3600) -> None:
        cutoff = time.time() - max_age_seconds
        stale_job_ids = [
            job_id for job_id, job in self._jobs.items() if job.created_at < cutoff
        ]

        for job_id in stale_job_ids:
            del self._jobs[job_id]

        if stale_job_ids:
            ui_print(
                "[frontend_jobs] cleaned up "
                + str(len(stale_job_ids))
                + " expired scrape jobs",
                debug=ui_settings.debug,
            )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _count_value(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if value is None:
        return 0
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    return _safe_int(value)


def _normalize_cached_via(cached_value: Any) -> list[str]:
    if cached_value is None:
        return []
    if isinstance(cached_value, list):
        return [str(item) for item in cached_value]
    if isinstance(cached_value, tuple):
        return [str(item) for item in cached_value]
    return []


def _size_gb(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def serialize_release(release_obj: Any, index: int) -> dict[str, Any]:
    cached_via = _normalize_cached_via(getattr(release_obj, "cached", []))

    files = getattr(release_obj, "files", [])
    if isinstance(files, (list, tuple)):
        file_count = len(files)
    else:
        file_count = 0

    return {
        "release_id": str(index),
        "title": str(getattr(release_obj, "title", "")),
        "source": str(getattr(release_obj, "source", "")),
        "type": str(getattr(release_obj, "type", "")),
        "size_gb": _size_gb(getattr(release_obj, "size", 0)),
        "seeders": _safe_int(getattr(release_obj, "seeders", 0)),
        "resolution": str(getattr(release_obj, "resolution", "")),
        "cached": len(cached_via) > 0,
        "cached_via": cached_via,
        "file_count": file_count,
        "wanted": _count_value(getattr(release_obj, "wanted", 0)),
        "unwanted": _count_value(getattr(release_obj, "unwanted", 0)),
    }


def serialize_releases(releases_list: list[Any]) -> list[dict[str, Any]]:
    return [
        serialize_release(release_obj, index)
        for index, release_obj in enumerate(releases_list)
    ]
