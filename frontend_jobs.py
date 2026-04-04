from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import regex

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
    season_number: int | None = None
    episode_number: int | None = None


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, ScrapeJob] = {}

    def create_job(
        self,
        tmdb_id: int,
        media_type: str,
        media_title: str,
        season_number: int | None = None,
        episode_number: int | None = None,
    ) -> str:
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = ScrapeJob(
            job_id=job_id,
            status="pending",
            media_type=media_type,
            media_title=media_title,
            tmdb_id=int(tmdb_id),
            season_number=season_number,
            episode_number=episode_number,
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


def _parse_release_meta(title: str) -> dict[str, Any]:
    """Parse common release metadata from a release title string."""
    t = title.upper()

    # Encode / source
    encode = ""
    for pat, label in [
        (r"\bREMUX\b", "REMUX"),
        (r"\bBLU-?RAY\b", "BluRay"),
        (r"\bWEB-?DL\b", "WEB-DL"),
        (r"\bWEBRIP\b", "WEBRip"),
        (r"\bHDTV\b", "HDTV"),
        (r"\bBDRIP\b", "BDRip"),
        (r"\bDVDRIP\b", "DVDRip"),
        (r"\bWEB\b", "WEB"),
    ]:
        if regex.search(pat, t):
            encode = label
            break

    # Video codec
    codec = ""
    for pat, label in [
        (r"\bAV1\b", "AV1"),
        (r"\bHEVC\b|\bH\.?265\b|\bX\.?265\b", "H.265"),
        (r"\bAVC\b|\bH\.?264\b|\bX\.?264\b", "H.264"),
        (r"\bVC-?1\b", "VC-1"),
    ]:
        if regex.search(pat, t):
            codec = label
            break

    # HDR / colour tags (can be multiple)
    hdr_tags: list[str] = []
    for pat, label in [
        (r"\bHDR10\+\b|\bHDR10PLUS\b", "HDR10+"),
        (r"\bDOLBY.?VISION\b|\bDOVI\b", "DV"),
        (r"\bHDR10\b", "HDR10"),
        (r"\bHDR\b", "HDR"),
        (r"\bHLG\b", "HLG"),
    ]:
        if regex.search(pat, t):
            hdr_tags.append(label)

    # Audio codec
    audio = ""
    for pat, label in [
        (r"\bTRUEHD.ATMOS\b|\bATMOS.TRUEHD\b", "TrueHD Atmos"),
        (r"\bATMOS\b", "Atmos"),
        (r"\bTRUEHD\b", "TrueHD"),
        (r"\bDTS-HD\.?MA\b", "DTS-HD MA"),
        (r"\bDTS-?X\b|\bDTSX\b", "DTS:X"),
        (r"\bDTS-HD\b", "DTS-HD"),
        (r"\bDTS\b", "DTS"),
        (r"\bEAC-?3\b|\bDD\+\b|\bDDP\b", "EAC3"),
        (r"\bAC-?3\b", "AC3"),
        (r"\bFLAC\b", "FLAC"),
        (r"\bAAC\b", "AAC"),
        (r"\bOPUS\b", "Opus"),
        (r"\bMP3\b", "MP3"),
    ]:
        if regex.search(pat, t):
            audio = label
            break

    # Audio channels
    channels = ""
    for pat, label in [
        (r"\b7\.1\.\d\b", "7.1.x"),
        (r"\b5\.1\.\d\b", "5.1.x"),
        (r"\b7\.1\b", "7.1"),
        (r"\b5\.1\b", "5.1"),
        (r"\b2\.0\b", "2.0"),
        (r"\bSTEREO\b", "Stereo"),
        (r"\bMONO\b", "Mono"),
    ]:
        if regex.search(pat, t):
            channels = label
            break

    # Release group — last hyphen token at end of title
    group = ""
    m = regex.search(
        r"-([A-Za-z0-9]{2,15})(?:\s*(?:\[|\(|\.(?:mkv|mp4|avi|ts))|$)", title
    )
    if m:
        group = m.group(1)

    return {
        "encode": encode,
        "codec": codec,
        "hdr_tags": hdr_tags,
        "audio": audio,
        "channels": channels,
        "group": group,
    }


def serialize_release(release_obj: Any, index: int) -> dict[str, Any]:
    cached_via = _normalize_cached_via(getattr(release_obj, "cached", []))

    files = getattr(release_obj, "files", [])
    if isinstance(files, (list, tuple)):
        file_count = len(files)
    else:
        file_count = 0

    title = str(getattr(release_obj, "title", ""))
    meta = _parse_release_meta(title)

    return {
        "release_id": str(index),
        "title": title,
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
        **meta,
    }


def serialize_releases(releases_list: list[Any]) -> list[dict[str, Any]]:
    return [
        serialize_release(release_obj, index)
        for index, release_obj in enumerate(releases_list)
    ]
