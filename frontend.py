"""
Simple web-based frontend for jellyfin_debrid
Serves UI on http://localhost:7654
"""

import os

from flask import Flask, jsonify, render_template, request

app = Flask(__name__, template_folder="templates")

LOG_FILE = "config/jellyfin_debrid.log"


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
