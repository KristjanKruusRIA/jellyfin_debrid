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
