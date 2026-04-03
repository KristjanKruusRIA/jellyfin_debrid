"""Tests for TMDB -> manual media object hydration."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _import_manual_media(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    manual_media_path = repo_root / "content" / "services" / "manual_media.py"

    for mod_name in [
        "content",
        "content.classes",
        "content.services",
        "content.services.manual_media",
        "ui",
        "ui.ui_print",
    ]:
        sys.modules.pop(mod_name, None)

    # Stub ui module used by service logging.
    ui_pkg = ModuleType("ui")
    ui_pkg.__path__ = []
    ui_print_mod = ModuleType("ui.ui_print")
    setattr(ui_print_mod, "ui_print", lambda *args, **kwargs: None)
    setattr(ui_print_mod, "ui_settings", SimpleNamespace(debug=True))
    setattr(ui_pkg, "ui_print", ui_print_mod)
    monkeypatch.setitem(sys.modules, "ui", ui_pkg)
    monkeypatch.setitem(sys.modules, "ui.ui_print", ui_print_mod)

    # Stub minimal content.classes.media behavior needed by the adapter tests.
    content_pkg = ModuleType("content")
    content_pkg.__path__ = [str(repo_root / "content")]
    classes_mod = ModuleType("content.classes")

    class _Media:
        type: str
        year: int
        parentTitle: str
        index: int
        grandparentTitle: str
        parentIndex: int
        Seasons: list
        Episodes: list

        def __init__(self, other):
            self.__dict__.update(other.__dict__)

        def query(self, title=""):
            normalized = (title or getattr(self, "title", "")).lower().replace(" ", ".")
            if self.type == "movie":
                return f"{normalized}.{self.year}"
            if self.type == "show":
                return normalized
            if self.type == "season":
                parent = self.parentTitle.lower().replace(" ", ".")
                return f"{parent}.S{self.index:02d}."
            parent = self.grandparentTitle.lower().replace(" ", ".")
            return f"{parent}.S{self.parentIndex:02d}E{self.index:02d}."

        def files(self):
            if self.type == "movie":
                return ["(mkv|mp4)"]
            if self.type == "show":
                files = []
                for season in self.Seasons:
                    files.extend(season.files())
                return files
            if self.type == "season":
                files = []
                for episode in self.Episodes:
                    files.extend(episode.files())
                return files
            return [f"S{self.parentIndex:02d}E{self.index:02d}"]

    setattr(classes_mod, "media", _Media)
    setattr(content_pkg, "classes", classes_mod)
    monkeypatch.setitem(sys.modules, "content", content_pkg)
    monkeypatch.setitem(sys.modules, "content.classes", classes_mod)

    services_pkg = ModuleType("content.services")
    services_pkg.__path__ = [str(repo_root / "content" / "services")]
    monkeypatch.setitem(sys.modules, "content.services", services_pkg)

    spec = importlib.util.spec_from_file_location(
        "content.services.manual_media", manual_media_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "content.services.manual_media", module)
    spec.loader.exec_module(module)
    return module


def test_build_manual_movie_has_title_year_eid_and_query_support(monkeypatch):
    manual_media = _import_manual_media(monkeypatch)

    details = {
        "id": 603,
        "title": "The Matrix",
        "release_date": "1999-03-30",
        "imdb_id": "tt0133093",
        "external_ids": {"imdb_id": "tt0133093"},
    }

    movie = manual_media.build_movie(details)

    assert movie.type == "movie"
    assert movie.title == "The Matrix"
    assert movie.year == 1999
    assert movie.EID["imdb"] == "tt0133093"
    assert movie.EID["tmdb"] == "603"
    assert movie.Releases == []
    assert movie.originallyAvailableAt == "1999-03-30"
    assert movie.query() == "the.matrix.1999"
    assert movie.files() == ["(mkv|mp4)"]


def test_build_manual_show_has_seasons_episodes_and_required_parent_fields(
    monkeypatch,
):
    manual_media = _import_manual_media(monkeypatch)

    details = {
        "id": 100,
        "title": "Dark",
        "first_air_date": "2017-12-01",
        "imdb_id": "tt5753856",
        "seasons": [
            {
                "season_number": 1,
                "episode_count": 2,
                "air_date": "2017-12-01",
            }
        ],
    }

    show = manual_media.build_show(details)

    assert show.type == "show"
    assert show.title == "Dark"
    assert show.year == 2017
    assert show.EID["imdb"] == "tt5753856"
    assert show.EID["tmdb"] == "100"
    assert len(show.Seasons) == 1

    season = show.Seasons[0]
    assert season.type == "season"
    assert season.index == 1
    assert season.parentTitle == "Dark"
    assert season.parentYear == 2017
    assert len(season.Episodes) == 2

    episode = season.Episodes[0]
    assert episode.type == "episode"
    assert episode.parentIndex == 1
    assert episode.index == 1
    assert episode.grandparentTitle == "Dark"
    assert episode.grandparentYear == 2017
    assert episode.query() == "dark.S01E01."

    wanted_files = show.files()
    assert any("S01E01" in pattern for pattern in wanted_files)


def test_manual_media_hydration_handles_missing_external_ids_gracefully(monkeypatch):
    manual_media = _import_manual_media(monkeypatch)

    movie_details = {
        "id": 12,
        "title": "No IDs Movie",
        "release_date": "2020-01-01",
    }

    show_details = {
        "id": 34,
        "title": "No IDs Show",
        "first_air_date": "2021-01-01",
        "seasons": [{"season_number": 1, "episode_count": 1}],
    }

    movie = manual_media.build_movie(movie_details)
    show = manual_media.build_show(show_details)

    assert movie.EID["imdb"] in ("", None)
    assert movie.EID["tmdb"] == "12"
    assert movie.query() == "no.ids.movie.2020"

    assert show.EID["imdb"] in ("", None)
    assert show.EID["tmdb"] == "34"
    assert len(show.Seasons) == 1
    assert len(show.Seasons[0].Episodes) == 1


def test_build_manual_season_has_required_fields_and_query(monkeypatch):
    manual_media = _import_manual_media(monkeypatch)

    show_details = {
        "id": 100,
        "title": "Dark",
        "first_air_date": "2017-12-01",
        "imdb_id": "tt5753856",
        "seasons": [
            {
                "season_number": 1,
                "episode_count": 2,
                "air_date": "2017-12-01",
            },
            {
                "season_number": 2,
                "episode_count": 3,
                "air_date": "2019-06-21",
            },
        ],
    }

    season = manual_media.build_season(show_details, 2)

    assert season.type == "season"
    assert season.index == 2
    assert season.parentTitle == "Dark"
    assert season.parentYear == 2017
    assert len(season.Episodes) == 3
    assert season.query() == "dark.S02."

    episode = season.Episodes[0]
    assert episode.type == "episode"
    assert episode.parentIndex == 2
    assert episode.grandparentTitle == "Dark"


def test_build_manual_season_falls_back_when_season_not_found(monkeypatch):
    manual_media = _import_manual_media(monkeypatch)

    show_details = {
        "id": 100,
        "title": "Dark",
        "first_air_date": "2017-12-01",
        "seasons": [
            {
                "season_number": 1,
                "episode_count": 2,
                "air_date": "2017-12-01",
            }
        ],
    }

    season = manual_media.build_season(show_details, 99)

    assert season.type == "season"
    assert season.index == 99
    assert season.parentTitle == "Dark"
    assert len(season.Episodes) == 0
