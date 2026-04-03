"""Thin TVDB v4 API wrapper for season enrichment."""

import time

import requests

from ui.ui_print import ui_print, ui_settings

name = "tvdb"
api_key = ""
pin = ""
_session = requests.Session()
_token: str | None = None
_token_expires_at: float = 0.0


def _is_token_valid() -> bool:
    if not _token:
        return False
    # Refresh 1 week before expiration, but we don't parse JWT here.
    # Simple heuristic: assume 1 month lifetime and refresh after 3 weeks.
    if time.time() < _token_expires_at:
        return True
    return False


def _login() -> str:
    global _token, _token_expires_at

    body: dict = {"apiKey": api_key}
    if pin:
        body["pin"] = pin

    try:
        ui_print("[tvdb] logging in to TVDB v4", debug=ui_settings.debug)
        response = _session.post(
            "https://api4.thetvdb.com/v4/login",
            json=body,
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json() if response else {}
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        new_token = data.get("token", "")
        if new_token:
            _token = str(new_token)
            # Assume ~3 weeks validity before refresh
            _token_expires_at = time.time() + (21 * 24 * 3600)
            ui_print("[tvdb] login successful", debug=ui_settings.debug)
            return _token
    except Exception as e:
        ui_print(f"[tvdb] login failed: {e}", debug=ui_settings.debug)

    return ""


def _ensure_token() -> str:
    if _is_token_valid() and _token:
        return _token
    return _login()


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _fetch_series_extended(tvdb_id: int):
    """Fetch raw extended series data from TVDB. Returns data dict or {}."""
    token = _ensure_token()
    if not token:
        ui_print("[tvdb] no valid token, skipping enrichment", debug=ui_settings.debug)
        return {}

    try:
        ui_print(
            f"[tvdb] fetching series extended data for tvdb_id={tvdb_id}",
            debug=ui_settings.debug,
        )
        response = _session.get(
            f"https://api4.thetvdb.com/v4/series/{tvdb_id}/extended",
            params={"meta": "episodes", "short": "true"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json() if response else {}
        return payload.get("data", {}) if isinstance(payload, dict) else {}
    except Exception as e:
        ui_print(
            f"[tvdb] failed to fetch series extended: {e}", debug=ui_settings.debug
        )
        return {}


def get_series_seasons(tvdb_id: int) -> list[int]:
    """Return sorted season numbers for a TVDB series ID, or empty list on failure."""
    data = _fetch_series_extended(tvdb_id)
    seasons = data.get("seasons", []) if isinstance(data, dict) else []

    season_numbers = set()
    for season in seasons:
        if not isinstance(season, dict):
            continue
        season_type = season.get("type")
        if isinstance(season_type, dict):
            if season_type.get("type") != "official":
                continue
        sn = _safe_int(season.get("number"), default=-1)
        if sn >= 0:
            season_numbers.add(sn)

    return sorted(season_numbers)


def get_season_details(tvdb_id: int, season_number: int) -> dict:
    """Return normalized season details for a TVDB series ID and season number.

    Returns a dict compatible with manual_media expectations:
    {"season_number": int, "episode_count": int, "air_date": str, "episodes": [...]}
    or {} on failure.
    """
    data = _fetch_series_extended(tvdb_id)
    if not data:
        return {}

    seasons = data.get("seasons", []) if isinstance(data, dict) else []
    episodes = data.get("episodes", []) if isinstance(data, dict) else []

    # Find the matching official season
    season = None
    for s in seasons:
        if not isinstance(s, dict):
            continue
        season_type = s.get("type")
        if isinstance(season_type, dict):
            if season_type.get("type") != "official":
                continue
        if _safe_int(s.get("number"), default=-1) == season_number:
            season = s
            break

    if season is None:
        ui_print(
            f"[tvdb] season {season_number} not found for tvdb_id={tvdb_id}",
            debug=ui_settings.debug,
        )
        return {}

    season_episodes = []
    for ep in episodes:
        if not isinstance(ep, dict):
            continue
        if _safe_int(ep.get("seasonNumber"), default=-1) == season_number:
            ep_number = _safe_int(ep.get("number"), default=0)
            if ep_number > 0:
                season_episodes.append(
                    {
                        "episode_number": ep_number,
                        "air_date": ep.get("aired") or "",
                    }
                )

    season_episodes.sort(key=lambda e: e["episode_number"])

    air_date = season.get("firstAired") or ""
    if not air_date and season_episodes:
        air_date = season_episodes[0].get("air_date") or ""

    return {
        "season_number": season_number,
        "episode_count": len(season_episodes),
        "air_date": air_date,
        "episodes": season_episodes,
    }
