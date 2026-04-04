"""
Simple web-based frontend for jellyfin_debrid
Serves UI on http://localhost:7654
"""

import os
import threading

import regex
from flask import Flask, jsonify, render_template, request

from frontend_jobs import JobRegistry, serialize_releases

app = Flask(__name__, template_folder="templates")

LOG_FILE = "config/jellyfin_debrid.log"
registry = JobRegistry()


def _json_error(message, status_code, **data):
    payload = {
        "status": "error",
        "error": message,
    }
    payload.update(data)
    return jsonify(payload), status_code


def _log_frontend(message):
    try:
        from ui import ui_settings
        from ui.ui_print import ui_print

        ui_print(f"[frontend] {message}", debug=ui_settings.debug)
    except Exception:
        pass


def _normalize_cached_via(cached_value):
    if isinstance(cached_value, list):
        return [str(item) for item in cached_value]
    if isinstance(cached_value, tuple):
        return [str(item) for item in cached_value]
    return []


def _filter_releases_for_season(releases, season_number):
    """Remove releases whose titles explicitly mention a different season."""
    if season_number is None:
        return releases

    filtered = []
    for release in releases:
        title = str(getattr(release, "title", ""))
        has_other_season = False
        for other in range(1, 30):
            if other == season_number:
                continue
            if regex.search(
                rf"(?<![0-9])(S0?{other}\b|season[ .]?0?{other}\b|TV-0?{other}\b)",
                title,
                regex.I,
            ):
                has_other_season = True
                break
        if not has_other_season:
            filtered.append(release)
    return filtered


def _run_scrape_job(
    job_registry, job_id, tmdb_id, media_type, season_number=None, episode_number=None
):
    try:
        job_registry.update_job(job_id, "running")

        import debrid
        import scraper
        from content.services import manual_media, tmdb, tvdb

        if media_type == "movie":
            details = tmdb.get_movie_details(tmdb_id)
            media_obj = manual_media.build_movie(details)
        elif episode_number is not None and season_number is not None:
            details = tmdb.get_show_details(tmdb_id)
            tvdb_id = None
            external_ids = details.get("external_ids")
            if isinstance(external_ids, dict):
                tvdb_id = external_ids.get("tvdb_id")

            season_details = None
            if tvdb_id:
                season_details = tvdb.get_season_details(int(tvdb_id), season_number)
            if not season_details:
                season_details = tmdb.get_season_details(tmdb_id, season_number)

            if season_details:
                existing = {s["season_number"] for s in details.get("seasons", [])}
                if season_details["season_number"] not in existing:
                    details.setdefault("seasons", []).append(season_details)
                else:
                    for s in details.get("seasons", []):
                        if s.get("season_number") == season_details["season_number"]:
                            s.update(season_details)
                            break
            media_obj = manual_media.build_episode(
                details, season_number, episode_number
            )
        elif season_number is not None:
            details = tmdb.get_show_details(tmdb_id)
            tvdb_id = None
            external_ids = details.get("external_ids")
            if isinstance(external_ids, dict):
                tvdb_id = external_ids.get("tvdb_id")

            season_details = None
            if tvdb_id:
                season_details = tvdb.get_season_details(int(tvdb_id), season_number)
            if not season_details:
                season_details = tmdb.get_season_details(tmdb_id, season_number)

            if season_details:
                existing = {s["season_number"] for s in details.get("seasons", [])}
                if season_details["season_number"] not in existing:
                    details.setdefault("seasons", []).append(season_details)
                else:
                    for s in details.get("seasons", []):
                        if s.get("season_number") == season_details["season_number"]:
                            s.update(season_details)
                            break
            media_obj = manual_media.build_season(details, season_number)
        else:
            details = tmdb.get_show_details(tmdb_id)
            tvdb_id = None
            external_ids = details.get("external_ids")
            if isinstance(external_ids, dict):
                tvdb_id = external_ids.get("tvdb_id")

            if tvdb_id:
                tvdb_season_numbers = tvdb.get_series_seasons(int(tvdb_id))
                if tvdb_season_numbers:
                    tvdb_seasons = []
                    for sn in tvdb_season_numbers:
                        sd = tvdb.get_season_details(int(tvdb_id), sn)
                        if sd:
                            tvdb_seasons.append(sd)
                    if tvdb_seasons:
                        details["seasons"] = tvdb_seasons

            media_obj = manual_media.build_show(details)

        query = media_obj.query()
        altquery = media_obj.deviation()
        imdb_id = None
        if hasattr(media_obj, "EID") and isinstance(media_obj.EID, dict):
            imdb_id = media_obj.EID.get("imdb") or None
        releases = scraper.scrape(query, altquery, imdb_id=imdb_id) or []

        if season_number is not None:
            releases = _filter_releases_for_season(releases, season_number)

        media_obj.Releases = list(releases)
        debrid.check(media_obj, force=True)

        # Apply anime filters so the manual search view matches auto-download behaviour
        import regex

        import releases as releases_mod

        if media_obj.isanime():
            if releases_mod.sort.anime_dub_filter == "true":
                media_obj.Releases = [
                    r
                    for r in media_obj.Releases
                    if regex.search(
                        releases_mod.sort.anime_dub_pattern, r.title, regex.I
                    )
                ]
            if releases_mod.sort.anime_hardsub_exclude == "true":
                media_obj.Releases = [
                    r
                    for r in media_obj.Releases
                    if not regex.search(
                        releases_mod.sort.anime_hardsub_pattern, r.title, regex.I
                    )
                ]
            groups = [
                g.strip()
                for g in releases_mod.sort.anime_preferred_groups.split(",")
                if g.strip()
            ]
            if groups:
                group_pattern = "|".join(regex.escape(g) for g in groups)
                media_obj.Releases.sort(
                    key=lambda r: bool(regex.search(group_pattern, r.title, regex.I)),
                    reverse=True,
                )
            if releases_mod.sort.anime_uncensored_prefer == "true":
                media_obj.Releases.sort(
                    key=lambda r: bool(regex.search(r"(?i)\buncensored\b", r.title)),
                    reverse=True,
                )

        job_registry.update_job(job_id, "complete", releases=media_obj.Releases)
    except Exception as e:
        _log_frontend(f"scrape job {job_id} failed: {str(e)}")
        job_registry.update_job(job_id, "failed", error="Scrape failed")


@app.route("/")
def index():
    return render_template("logs.html")


@app.route("/search")
def search_page():
    return render_template("search.html")


@app.route("/api/logs")
def get_logs():
    """Get logs as JSON"""
    if not os.path.exists(LOG_FILE):
        return jsonify(
            {"content": "Log file not found. Service may not be running yet.\n"}
        )

    try:
        with open(LOG_FILE, "rb") as f:
            content = f.read()
            text = content.decode("utf-8", errors="replace")
            all_lines = text.split("\n")
            # Return last 200 lines
            logs = "\n".join(all_lines[-200:])
            return jsonify({"content": logs})
    except Exception as e:
        return jsonify({"content": f"Error reading log file: {str(e)}\n"})


@app.route("/api/search")
def search_api():
    """Search TMDB for movies and TV series."""
    q = request.args.get("q", "").strip()
    if not q:
        return (
            jsonify(
                {
                    "query": "",
                    "results": [],
                    "count": 0,
                    "error": "Missing required parameter: q",
                }
            ),
            400,
        )

    media_type = request.args.get("type")
    if media_type not in (None, "all", "movie", "tv"):
        media_type = None
    if media_type == "all":
        media_type = None

    try:
        from content.services import tmdb

        result = tmdb.search(q, media_type=media_type)
        results = result.get("results", [])
        return jsonify(
            {
                "query": q,
                "results": results,
                "count": len(results),
                "error": result.get("error"),
            }
        )
    except Exception:
        return jsonify(
            {
                "query": q,
                "results": [],
                "count": 0,
                "error": "Search service unavailable",
            }
        )


@app.route("/api/tmdb/<media_type>/<tmdb_id>", methods=["GET"])
def tmdb_lookup_api(media_type, tmdb_id):
    if media_type not in ("movie", "tv"):
        return _json_error(
            "Invalid media_type. Expected one of: movie, tv",
            400,
        )

    try:
        parsed_tmdb_id = int(tmdb_id)
    except (TypeError, ValueError):
        return _json_error("Invalid tmdb_id. Expected an integer", 400)

    try:
        from content.services import tmdb, tvdb

        if media_type == "movie":
            details = tmdb.get_movie_details(parsed_tmdb_id)
        else:
            details = tmdb.get_show_details(parsed_tmdb_id)

        if not details:
            return _json_error("TMDB item not found", 404)

        year = details.get("year")
        result = {
            "id": details.get("id", parsed_tmdb_id),
            "title": details.get("title", ""),
            "year": "" if year is None else str(year),
            "media_type": media_type,
            "poster_path": details.get("poster_path"),
            "overview": details.get("overview", ""),
        }
        if media_type == "tv":
            raw_seasons = details.get("seasons", [])
            seasons = []
            for s in raw_seasons:
                if isinstance(s, dict):
                    sn = s.get("season_number")
                    if sn is not None:
                        try:
                            seasons.append(int(sn))
                        except (TypeError, ValueError):
                            pass

            # Try TVDB enrichment for more accurate season counts
            external_ids = details.get("external_ids", {})
            tvdb_id = (
                external_ids.get("tvdb_id") if isinstance(external_ids, dict) else None
            )
            if tvdb_id:
                try:
                    tvdb_seasons = tvdb.get_series_seasons(int(tvdb_id))
                    if tvdb_seasons:
                        seasons = tvdb_seasons
                except Exception:
                    pass

            result["seasons"] = sorted(set(seasons))
        return jsonify(result)
    except Exception as e:
        _log_frontend(
            f"tmdb lookup failed for media_type={media_type}, tmdb_id={tmdb_id}:"
            f" {str(e)}"
        )
        return _json_error("TMDB lookup service unavailable", 500)


@app.route("/api/tmdb/tv/<tmdb_id>/season/<season_number>", methods=["GET"])
def tmdb_season_lookup_api(tmdb_id, season_number):
    try:
        parsed_tmdb_id = int(tmdb_id)
        parsed_season_number = int(season_number)
    except (TypeError, ValueError):
        return _json_error("Invalid tmdb_id or season_number", 400)

    try:
        from content.services import tmdb, tvdb

        # Try TVDB first (it may have seasons TMDB doesn't, e.g. split-cour shows)
        season_details = None
        show_details = tmdb.get_show_details(parsed_tmdb_id)
        tvdb_id = None
        external_ids = show_details.get("external_ids") if show_details else None
        if isinstance(external_ids, dict):
            tvdb_id = external_ids.get("tvdb_id")
        if tvdb_id:
            season_details = tvdb.get_season_details(int(tvdb_id), parsed_season_number)
        if not season_details:
            season_details = tmdb.get_season_details(
                parsed_tmdb_id, parsed_season_number
            )
        if not season_details:
            return _json_error("Season not found", 404)

        episodes = []
        for ep in season_details.get("episodes", []):
            if isinstance(ep, dict):
                episodes.append(
                    {
                        "episode_number": ep.get("episode_number"),
                        "air_date": ep.get("air_date"),
                    }
                )

        return jsonify(
            {
                "season_number": season_details.get("season_number"),
                "episode_count": season_details.get("episode_count"),
                "episodes": episodes,
            }
        )
    except Exception as e:
        _log_frontend(
            f"tmdb season lookup failed for tmdb_id={tmdb_id},"
            f" season_number={season_number}: {str(e)}"
        )
        return _json_error("TMDB lookup service unavailable", 500)


@app.route("/api/scrapes", methods=["POST"])
def create_scrape():
    try:
        body = request.get_json(silent=True) or {}
        tmdb_id_raw = body.get("tmdb_id")
        media_type = body.get("media_type")
        media_title = (body.get("title") or "").strip()
        season_number_raw = body.get("season_number")
        episode_number_raw = body.get("episode_number")

        try:
            tmdb_id = int(tmdb_id_raw)
        except (TypeError, ValueError):
            return _json_error(
                "Invalid or missing required field: tmdb_id",
                400,
                job_id=None,
            )

        if media_type not in ("movie", "tv"):
            return _json_error(
                "Invalid or missing required field: media_type",
                400,
                job_id=None,
            )

        season_number = None
        if season_number_raw is not None:
            try:
                season_number = int(season_number_raw)
                if season_number < 0:
                    season_number = None
            except (TypeError, ValueError):
                season_number = None

        episode_number = None
        if episode_number_raw is not None:
            try:
                episode_number = int(episode_number_raw)
                if episode_number < 1:
                    episode_number = None
            except (TypeError, ValueError):
                episode_number = None

        if not media_title:
            media_title = f"TMDB {tmdb_id}"

        job_id = registry.create_job(
            tmdb_id=tmdb_id,
            media_type=media_type,
            media_title=media_title,
            season_number=season_number,
            episode_number=episode_number,
        )

        thread = threading.Thread(
            target=_run_scrape_job,
            args=(registry, job_id, tmdb_id, media_type, season_number, episode_number),
            daemon=True,
        )
        thread.start()

        return (
            jsonify(
                {
                    "status": "running",
                    "error": None,
                    "job_id": job_id,
                }
            ),
            202,
        )
    except Exception as e:
        _log_frontend(f"failed to create scrape job: {str(e)}")
        return _json_error("Failed to start scrape job", 500, job_id=None)


@app.route("/api/scrapes/<job_id>", methods=["GET"])
def get_scrape_status(job_id):
    try:
        job = registry.get_job(job_id)
        if job is None:
            return _json_error(
                "Scrape job not found",
                404,
                job_id=job_id,
                media=None,
                results=[],
                count=0,
            )

        results = serialize_releases(job.releases)
        return jsonify(
            {
                "status": job.status,
                "error": job.error,
                "job_id": job.job_id,
                "media": {
                    "title": job.media_title,
                    "type": job.media_type,
                    "tmdb_id": job.tmdb_id,
                    "season_number": job.season_number,
                    "episode_number": job.episode_number,
                },
                "results": results,
                "count": len(results),
            }
        )
    except Exception as e:
        _log_frontend(f"failed to fetch scrape status for {job_id}: {str(e)}")
        return _json_error(
            "Failed to fetch scrape status",
            500,
            job_id=job_id,
            media=None,
            results=[],
            count=0,
        )


@app.route("/api/scrapes/<job_id>/downloads", methods=["POST"])
def download_scrape_release(job_id):
    try:
        body = request.get_json(silent=True) or {}
        release_id = body.get("release_id")
        if release_id is None or str(release_id).strip() == "":
            return _json_error(
                "Missing required field: release_id",
                400,
                job_id=job_id,
            )

        job = registry.get_job(job_id)
        if job is None:
            return _json_error("Scrape job not found", 404, job_id=job_id)

        selected_release = registry.get_release(job_id, str(release_id))
        if selected_release is None:
            return _json_error(
                "Release not found for scrape job",
                404,
                job_id=job_id,
                release_id=str(release_id),
            )

        import debrid
        from content.services import manual_media, tmdb, tvdb

        if job.media_type == "movie":
            details = tmdb.get_movie_details(job.tmdb_id)
            media_obj = manual_media.build_movie(details)
        elif job.episode_number is not None and job.season_number is not None:
            details = tmdb.get_show_details(job.tmdb_id)
            tvdb_id = None
            external_ids = details.get("external_ids")
            if isinstance(external_ids, dict):
                tvdb_id = external_ids.get("tvdb_id")

            season_details = None
            if tvdb_id:
                season_details = tvdb.get_season_details(
                    int(tvdb_id), job.season_number
                )
            if not season_details:
                season_details = tmdb.get_season_details(job.tmdb_id, job.season_number)

            if season_details:
                existing = {s["season_number"] for s in details.get("seasons", [])}
                if season_details["season_number"] not in existing:
                    details.setdefault("seasons", []).append(season_details)
                else:
                    for s in details.get("seasons", []):
                        if s.get("season_number") == season_details["season_number"]:
                            s.update(season_details)
                            break
            media_obj = manual_media.build_episode(
                details, job.season_number, job.episode_number
            )
        elif job.season_number is not None:
            details = tmdb.get_show_details(job.tmdb_id)
            tvdb_id = None
            external_ids = details.get("external_ids")
            if isinstance(external_ids, dict):
                tvdb_id = external_ids.get("tvdb_id")

            season_details = None
            if tvdb_id:
                season_details = tvdb.get_season_details(
                    int(tvdb_id), job.season_number
                )
            if not season_details:
                season_details = tmdb.get_season_details(job.tmdb_id, job.season_number)

            if season_details:
                existing = {s["season_number"] for s in details.get("seasons", [])}
                if season_details["season_number"] not in existing:
                    details.setdefault("seasons", []).append(season_details)
                else:
                    for s in details.get("seasons", []):
                        if s.get("season_number") == season_details["season_number"]:
                            s.update(season_details)
                            break
            media_obj = manual_media.build_season(details, job.season_number)
        else:
            details = tmdb.get_show_details(job.tmdb_id)
            tvdb_id = None
            external_ids = details.get("external_ids")
            if isinstance(external_ids, dict):
                tvdb_id = external_ids.get("tvdb_id")

            if tvdb_id:
                tvdb_season_numbers = tvdb.get_series_seasons(int(tvdb_id))
                if tvdb_season_numbers:
                    tvdb_seasons = []
                    for sn in tvdb_season_numbers:
                        sd = tvdb.get_season_details(int(tvdb_id), sn)
                        if sd:
                            tvdb_seasons.append(sd)
                    if tvdb_seasons:
                        details["seasons"] = tvdb_seasons

            media_obj = manual_media.build_show(details)

        media_obj.Releases = [selected_release]
        debrid.download(media_obj, query=media_obj.query(), force=True)

        cached_via = _normalize_cached_via(getattr(selected_release, "cached", []))
        release_title = str(getattr(selected_release, "title", "selected release"))
        return jsonify(
            {
                "status": "started",
                "error": None,
                "job_id": job_id,
                "release_id": str(release_id),
                "message": f"Download started for: {release_title}",
                "cached": len(cached_via) > 0,
                "cached_via": cached_via,
            }
        )
    except Exception as e:
        _log_frontend(f"failed to start download for job {job_id}: {str(e)}")
        return _json_error("Download failed", 500, job_id=job_id)


def start_frontend():
    """Start the log viewer in the current thread (use as a daemon thread target)."""
    port = int(os.environ.get("FRONTEND_PORT", "7654"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    print("=" * 60)
    print("Jellyfin Debrid Log Viewer")
    print("=" * 60)
    print("Open your browser to: http://localhost:7654")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    start_frontend()
