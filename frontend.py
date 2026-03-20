"""
Simple web-based frontend for jellyfin_debrid
Serves UI on http://localhost:7654
"""

import os
import threading

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


def _run_scrape_job(job_registry, job_id, tmdb_id, media_type):
    try:
        job_registry.update_job(job_id, "running")

        import debrid
        import scraper
        from content.services import manual_media, tmdb

        if media_type == "movie":
            details = tmdb.get_movie_details(tmdb_id)
            media_obj = manual_media.build_movie(details)
        else:
            details = tmdb.get_show_details(tmdb_id)
            media_obj = manual_media.build_show(details)

        query = media_obj.query()
        altquery = media_obj.deviation()
        releases = scraper.scrape(query, altquery) or []

        media_obj.Releases = list(releases)
        debrid.check(media_obj, force=True)

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
        from content.services import tmdb

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
        return jsonify(result)
    except Exception as e:
        _log_frontend(
            f"tmdb lookup failed for media_type={media_type}, tmdb_id={tmdb_id}:"
            f" {str(e)}"
        )
        return _json_error("TMDB lookup service unavailable", 500)


@app.route("/api/scrapes", methods=["POST"])
def create_scrape():
    try:
        body = request.get_json(silent=True) or {}
        tmdb_id_raw = body.get("tmdb_id")
        media_type = body.get("media_type")
        media_title = (body.get("title") or "").strip()

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

        if not media_title:
            media_title = f"TMDB {tmdb_id}"

        job_id = registry.create_job(
            tmdb_id=tmdb_id,
            media_type=media_type,
            media_title=media_title,
        )

        thread = threading.Thread(
            target=_run_scrape_job,
            args=(registry, job_id, tmdb_id, media_type),
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
        from content.services import manual_media, tmdb

        if job.media_type == "movie":
            details = tmdb.get_movie_details(job.tmdb_id)
            media_obj = manual_media.build_movie(details)
        else:
            details = tmdb.get_show_details(job.tmdb_id)
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
    app.run(host="0.0.0.0", port=7654, debug=False, threaded=True)


if __name__ == "__main__":
    print("=" * 60)
    print("Jellyfin Debrid Log Viewer")
    print("=" * 60)
    print("Open your browser to: http://localhost:7654")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    start_frontend()
