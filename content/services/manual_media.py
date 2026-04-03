from types import SimpleNamespace
from typing import Any

from content import classes
from ui.ui_print import ui_print, ui_settings

DEFAULT_AIR_DATE = "1990-01-01"


class ExternalIDs(dict):
    """Dictionary-like external IDs that also iterates as legacy EID strings."""

    def _as_scheme_ids(self) -> list[str]:
        ids: list[str] = []
        imdb_id = self.get("imdb")
        tmdb_id = self.get("tmdb")
        tvdb_id = self.get("tvdb")

        if imdb_id:
            ids.append(f"imdb://{imdb_id}")
        if tmdb_id:
            ids.append(f"tmdb://{tmdb_id}")
        if tvdb_id:
            ids.append(f"tvdb://{tvdb_id}")

        return ids

    def __iter__(self):  # type: ignore[override]
        return iter(self._as_scheme_ids())

    def __contains__(self, item):  # type: ignore[override]
        return dict.__contains__(self, item) or item in self._as_scheme_ids()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _extract_year(date_value: str) -> int:
    if not isinstance(date_value, str) or len(date_value) < 4:
        return 0
    return _to_int(date_value[:4], default=0)


def _safe_date(date_value: Any) -> str:
    if isinstance(date_value, str) and date_value:
        return date_value
    return DEFAULT_AIR_DATE


def _build_eid(tmdb_details: dict[str, Any]) -> ExternalIDs:
    external_ids = tmdb_details.get("external_ids")
    if not isinstance(external_ids, dict):
        external_ids = {}

    imdb_id = (
        tmdb_details.get("imdb_id")
        or external_ids.get("imdb_id")
        or external_ids.get("imdb")
        or ""
    )
    tmdb_id = tmdb_details.get("id") or tmdb_details.get("tmdb_id") or ""
    tvdb_id = external_ids.get("tvdb_id") or ""

    return ExternalIDs(
        {
            "imdb": str(imdb_id) if imdb_id else "",
            "tmdb": str(tmdb_id) if tmdb_id else "",
            "tvdb": str(tvdb_id) if tvdb_id else "",
        }
    )


def build_movie(tmdb_details: dict[str, Any]) -> classes.media:
    title = tmdb_details.get("title") or ""
    release_date = _safe_date(tmdb_details.get("release_date"))

    movie = SimpleNamespace()
    movie.type = "movie"
    movie.title = title
    movie.year = _extract_year(release_date)
    movie.EID = _build_eid(tmdb_details)
    movie.Releases = []
    movie.originallyAvailableAt = release_date

    ui_print(
        f"[manual_media] built movie context for '{movie.title}'",
        debug=ui_settings.debug,
    )
    return classes.media(movie)


def _iter_episode_numbers(season: dict[str, Any]) -> list[dict[str, Any]]:
    episodes = season.get("episodes")
    if isinstance(episodes, list) and episodes:
        normalized: list[dict[str, Any]] = []
        for episode in episodes:
            if not isinstance(episode, dict):
                continue
            episode_number = _to_int(episode.get("episode_number"), default=0)
            if episode_number <= 0:
                continue
            normalized.append(
                {
                    "episode_number": episode_number,
                    "air_date": episode.get("air_date"),
                }
            )
        if normalized:
            return normalized

    episode_count = _to_int(season.get("episode_count"), default=0)
    if episode_count <= 0:
        episode_count = 1

    return [
        {
            "episode_number": episode_number,
            "air_date": season.get("air_date"),
        }
        for episode_number in range(1, episode_count + 1)
    ]


def _build_single_season(
    show: SimpleNamespace, season_data: dict[str, Any]
) -> classes.media:
    season_number = _to_int(season_data.get("season_number"), default=0)

    season = SimpleNamespace()
    season.type = "season"
    season.index = season_number
    season.parentEID = show.EID
    season.parentTitle = show.title
    season.parentYear = show.year
    season.Episodes = []

    for episode_data in _iter_episode_numbers(season_data):
        episode = SimpleNamespace()
        episode.type = "episode"
        episode.index = _to_int(episode_data.get("episode_number"), default=1)
        episode.parentIndex = season_number
        episode.grandparentEID = show.EID
        episode.grandparentTitle = show.title
        episode.grandparentYear = show.year
        episode.originallyAvailableAt = _safe_date(
            episode_data.get("air_date")
            or season_data.get("air_date")
            or show.originallyAvailableAt
        )
        season.Episodes.append(classes.media(episode))

    return classes.media(season)


def build_show(tmdb_details: dict[str, Any]) -> classes.media:
    title = tmdb_details.get("title") or tmdb_details.get("name") or ""
    first_air_date = _safe_date(tmdb_details.get("first_air_date"))

    show = SimpleNamespace()
    show.type = "show"
    show.title = title
    show.year = _extract_year(first_air_date)
    show.EID = _build_eid(tmdb_details)
    show.originallyAvailableAt = first_air_date
    show.Seasons = []

    seasons = tmdb_details.get("seasons")
    if not isinstance(seasons, list):
        seasons = []

    for season_data in seasons:
        if not isinstance(season_data, dict):
            continue

        season_number = _to_int(season_data.get("season_number"), default=0)
        if season_number <= 0:
            continue

        show.Seasons.append(_build_single_season(show, season_data))

    ui_print(
        f"[manual_media] built show context for '{show.title}' with "
        f"{len(show.Seasons)} seasons",
        debug=ui_settings.debug,
    )
    return classes.media(show)


def build_season(tmdb_details: dict[str, Any], season_number: int) -> classes.media:
    title = tmdb_details.get("title") or tmdb_details.get("name") or ""
    first_air_date = _safe_date(tmdb_details.get("first_air_date"))

    show = SimpleNamespace()
    show.type = "show"
    show.title = title
    show.year = _extract_year(first_air_date)
    show.EID = _build_eid(tmdb_details)
    show.originallyAvailableAt = first_air_date

    seasons = tmdb_details.get("seasons")
    if not isinstance(seasons, list):
        seasons = []

    season_data = None
    for s in seasons:
        if isinstance(s, dict) and _to_int(s.get("season_number")) == season_number:
            season_data = s
            break

    if season_data is not None:
        season = _build_single_season(show, season_data)
    else:
        ns = SimpleNamespace()
        ns.type = "season"
        ns.index = season_number
        ns.parentEID = show.EID
        ns.parentTitle = show.title
        ns.parentYear = show.year
        ns.Episodes = []
        season = classes.media(ns)

    ui_print(
        f"[manual_media] built season {season_number} context for '{show.title}'"
        f" with {len(getattr(season, 'Episodes', []))} episodes",
        debug=ui_settings.debug,
    )
    return season


def build_episode(
    tmdb_details: dict[str, Any], season_number: int, episode_number: int
) -> classes.media:
    title = tmdb_details.get("title") or tmdb_details.get("name") or ""
    first_air_date = _safe_date(tmdb_details.get("first_air_date"))

    show = SimpleNamespace()
    show.type = "show"
    show.title = title
    show.year = _extract_year(first_air_date)
    show.EID = _build_eid(tmdb_details)
    show.originallyAvailableAt = first_air_date

    seasons = tmdb_details.get("seasons")
    if not isinstance(seasons, list):
        seasons = []

    season_data = None
    for s in seasons:
        if isinstance(s, dict) and _to_int(s.get("season_number")) == season_number:
            season_data = s
            break

    episode = SimpleNamespace()
    episode.type = "episode"
    episode.index = episode_number
    episode.parentIndex = season_number
    episode.grandparentEID = show.EID
    episode.grandparentTitle = show.title
    episode.grandparentYear = show.year

    air_date = first_air_date
    if season_data:
        for ep in season_data.get("episodes", []):
            if (
                isinstance(ep, dict)
                and _to_int(ep.get("episode_number")) == episode_number
            ):
                air_date = _safe_date(ep.get("air_date")) or air_date
                break
        if not air_date:
            air_date = _safe_date(season_data.get("air_date")) or first_air_date

    episode.originallyAvailableAt = air_date

    ui_print(
        f"[manual_media] built S{season_number:02d}E{episode_number:02d} context for"
        f" '{show.title}'",
        debug=ui_settings.debug,
    )
    return classes.media(episode)
