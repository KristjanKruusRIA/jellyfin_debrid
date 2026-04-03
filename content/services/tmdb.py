from urllib.parse import urlencode

import requests

from ui.ui_print import ui_print, ui_settings

name = "tmdb"
api_key = ""
session = requests.Session()


def _normalize_result(result):
    media_type = result.get("media_type")
    if media_type not in ("movie", "tv"):
        return None

    if media_type == "movie":
        title = result.get("title") or ""
        date_value = result.get("release_date") or ""
    else:
        title = result.get("name") or ""
        date_value = result.get("first_air_date") or ""

    year = date_value[:4] if date_value else ""

    try:
        item_id = int(result.get("id", 0))
    except Exception:
        item_id = 0

    return {
        "id": item_id,
        "title": title,
        "year": year,
        "media_type": media_type,
        "poster_path": result.get("poster_path"),
        "overview": result.get("overview") or "",
    }


def _to_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _safe_date(date_value):
    if isinstance(date_value, str):
        return date_value
    return ""


def _sanitize_error(error):
    error_text = str(error)
    if api_key and api_key in error_text:
        error_text = error_text.replace(api_key, "***")
    return error_text


def _request_details(path, label):
    if not api_key:
        ui_print("[tmdb] TMDB API Key not configured", debug=ui_settings.debug)
        return {}

    params = urlencode({"api_key": api_key, "append_to_response": "external_ids"})
    url = f"https://api.themoviedb.org/3/{path}?{params}"

    try:
        ui_print(f"[tmdb] fetching {label} details", debug=ui_settings.debug)
        response = session.get(url, timeout=10)
        response.raise_for_status()
        payload = response.json() if response else {}
        return payload if isinstance(payload, dict) else {}
    except Exception as error:
        message = f"TMDB {label} details failed: {_sanitize_error(error)}"
        ui_print(f"[tmdb] {message}", debug=ui_settings.debug)
        return {}


def _normalize_external_ids(payload):
    external_ids = payload.get("external_ids")
    if not isinstance(external_ids, dict):
        external_ids = {}

    imdb_id = external_ids.get("imdb_id") or payload.get("imdb_id") or ""

    return external_ids, imdb_id


def _normalize_seasons(raw_seasons):
    if not isinstance(raw_seasons, list):
        return []

    seasons = []
    for season in raw_seasons:
        if not isinstance(season, dict):
            continue

        season_number = _to_int(season.get("season_number"), default=0)
        if season_number <= 0:
            continue

        air_date = _safe_date(season.get("air_date"))
        episode_count = _to_int(season.get("episode_count"), default=0)

        episodes = []
        raw_episodes = season.get("episodes")
        if isinstance(raw_episodes, list) and len(raw_episodes) > 0:
            for episode in raw_episodes:
                if not isinstance(episode, dict):
                    continue
                episode_number = _to_int(episode.get("episode_number"), default=0)
                if episode_number <= 0:
                    continue
                episodes.append(
                    {
                        "episode_number": episode_number,
                        "air_date": _safe_date(episode.get("air_date")) or air_date,
                    }
                )
        else:
            for episode_number in range(1, episode_count + 1):
                episodes.append(
                    {
                        "episode_number": episode_number,
                        "air_date": air_date,
                    }
                )

        seasons.append(
            {
                "season_number": season_number,
                "episode_count": episode_count,
                "air_date": air_date,
                "episodes": episodes,
            }
        )

    return seasons


def search(query, media_type=None):
    """Search TMDB. Returns {'results': [...], 'error': None} or error dict."""
    if not api_key:
        ui_print("[tmdb] TMDB API Key not configured", debug=ui_settings.debug)
        return {"results": [], "error": "TMDB API Key not configured"}

    params = urlencode({"api_key": api_key, "query": query})
    url = f"https://api.themoviedb.org/3/search/multi?{params}"

    try:
        ui_print("[tmdb] searching TMDB", debug=ui_settings.debug)
        response = session.get(url, timeout=10)
        response.raise_for_status()
        payload = response.json() if response else {}
        raw_results = payload.get("results", []) if isinstance(payload, dict) else []

        normalized_results = []
        for result in raw_results:
            if not isinstance(result, dict):
                continue
            normalized = _normalize_result(result)
            if normalized is None:
                continue
            if media_type in ("movie", "tv") and normalized["media_type"] != media_type:
                continue
            normalized_results.append(normalized)

        return {"results": normalized_results, "error": None}
    except Exception as error:
        error_text = str(error)
        if api_key and api_key in error_text:
            error_text = error_text.replace(api_key, "***")
        message = f"TMDB search failed: {error_text}"
        ui_print(f"[tmdb] {message}", debug=ui_settings.debug)
        return {"results": [], "error": message}


def get_movie_details(tmdb_id):
    payload = _request_details(f"movie/{tmdb_id}", "movie")
    if not payload:
        return {}

    external_ids, imdb_id = _normalize_external_ids(payload)
    release_date = _safe_date(payload.get("release_date"))

    return {
        "id": _to_int(payload.get("id"), default=_to_int(tmdb_id)),
        "title": payload.get("title") or "",
        "year": release_date[:4] if release_date else "",
        "release_date": release_date,
        "imdb_id": imdb_id,
        "external_ids": external_ids,
        "poster_path": payload.get("poster_path"),
        "overview": payload.get("overview") or "",
    }


def get_show_details(tmdb_id):
    payload = _request_details(f"tv/{tmdb_id}", "show")
    if not payload:
        return {}

    external_ids, imdb_id = _normalize_external_ids(payload)
    first_air_date = _safe_date(payload.get("first_air_date"))

    return {
        "id": _to_int(payload.get("id"), default=_to_int(tmdb_id)),
        "title": payload.get("name") or "",
        "year": first_air_date[:4] if first_air_date else "",
        "first_air_date": first_air_date,
        "imdb_id": imdb_id,
        "external_ids": external_ids,
        "seasons": _normalize_seasons(payload.get("seasons")),
        "poster_path": payload.get("poster_path"),
        "overview": payload.get("overview") or "",
    }


def get_season_details(tmdb_id, season_number):
    """Fetch season details for a show. Returns normalized season dict or {}."""
    if not api_key:
        ui_print("[tmdb] TMDB API Key not configured", debug=ui_settings.debug)
        return {}

    params = urlencode({"api_key": api_key})
    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season_number}?{params}"

    try:
        ui_print(
            f"[tmdb] fetching season {season_number} details for tv/{tmdb_id}",
            debug=ui_settings.debug,
        )
        response = session.get(url, timeout=10)
        if response.status_code == 404:
            ui_print(
                f"[tmdb] season {season_number} not found on TMDB for tv/{tmdb_id}",
                debug=ui_settings.debug,
            )
            return {}
        response.raise_for_status()
        payload = response.json() if response else {}
        if not isinstance(payload, dict):
            return {}

        episodes = []
        raw_episodes = payload.get("episodes")
        if isinstance(raw_episodes, list):
            for episode in raw_episodes:
                if not isinstance(episode, dict):
                    continue
                episode_number = _to_int(episode.get("episode_number"), default=0)
                if episode_number <= 0:
                    continue
                episodes.append(
                    {
                        "episode_number": episode_number,
                        "air_date": _safe_date(episode.get("air_date")),
                    }
                )

        air_date = _safe_date(payload.get("air_date"))
        episode_count = (
            len(episodes)
            if episodes
            else _to_int(payload.get("episode_count"), default=0)
        )

        if not episodes and episode_count > 0:
            for episode_number in range(1, episode_count + 1):
                episodes.append(
                    {
                        "episode_number": episode_number,
                        "air_date": air_date,
                    }
                )

        return {
            "season_number": _to_int(payload.get("season_number"), default=0),
            "episode_count": episode_count,
            "air_date": air_date,
            "episodes": episodes,
        }
    except Exception as e:
        message = f"TMDB season details failed: {_sanitize_error(e)}"
        ui_print(f"[tmdb] {message}", debug=ui_settings.debug)
        return {}


def resolve_imdb_id(query, media_type="movie"):
    """Resolve a text query to an IMDB ID via TMDB search + details.

    Args:
        query: Title text to search for (may be dotted like "war.of.the.worlds.2025").
        media_type: "movie", "show" or "season".

    Returns:
        IMDB ID string (e.g. "tt1234567") or None if not found.
    """
    import re

    # Normalize dotted scraper queries: "war.of.the.worlds.2025" → "war of the worlds"
    clean = query.replace(".", " ").strip()
    clean = re.sub(r"\s+(19|20)\d{2}\s*$", "", clean).strip()

    # Strip season/episode markers for show/season searches so TMDB can find the series
    if media_type in ("show", "season"):
        clean = re.sub(r"\s+S\d+(?:E\d+)?\s*$", "", clean, flags=re.IGNORECASE).strip()

    tmdb_type = "tv" if media_type in ("show", "season") else "movie"
    result = search(clean, media_type=tmdb_type)
    results = result.get("results", [])
    if not results:
        return None

    tmdb_id = results[0].get("id")
    if not tmdb_id:
        return None

    if tmdb_type == "movie":
        details = get_movie_details(tmdb_id)
    else:
        details = get_show_details(tmdb_id)

    return details.get("imdb_id") or None
