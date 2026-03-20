# import modules
import json
from types import SimpleNamespace

import regex
import requests

import downloader
from ui.ui_print import ui_print, ui_settings

# (required) Name of the Debrid service
name = "Real Debrid"
short = "RD"
# (required) Authentification of the Debrid service.
api_key = ""
# Define Variables
session = requests.Session()
errors = [
    [202, " action already done"],
    [400, " bad Request (see error message)"],
    [403, " permission denied (infringing torrent or account locked or not premium)"],
    [503, " service unavailable (see error message)"],
    [404, " wrong parameter (invalid file id(s)) / unknown ressource (invalid id)"],
]


def setup(cls, new=False):
    from debrid.services import setup

    setup(cls, new)


# Error Log
def logerror(response, context=None):
    if response.status_code not in [200, 201, 204]:
        desc = ""
        for error in errors:
            if response.status_code == error[0]:
                desc = error[1]
        extra = (" Context: " + str(context)) if context else ""
        ui_print(
            "[realdebrid] error: ("
            + str(response.status_code)
            + desc
            + ") "
            + str(response.content)
            + extra,
            debug=ui_settings.debug,
        )
    if response.status_code == 401:
        ui_print(
            "[realdebrid] error: (401 unauthorized): realdebrid api key does not seem to work. check your realdebrid settings."
            + (" Context: " + str(context) if context else "")
        )
    if response.status_code == 403:
        ui_print(
            "[realdebrid] error: (403 unauthorized): You may have attempted to add an infringing torrent or your realdebrid account is locked or you dont have premium."
            + (" Context: " + str(context) if context else "")
        )


# Get Function
def get(url, context=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36",
        "authorization": "Bearer " + api_key,
    }
    response = None
    try:
        response = session.get(url, headers=headers)
        logerror(response, context)
        response = json.loads(
            response.content, object_hook=lambda d: SimpleNamespace(**d)
        )
    except Exception as e:
        ui_print(
            "[realdebrid] error: (json exception): " + str(e), debug=ui_settings.debug
        )
        response = None
    return response


# Post Function
def post(url, data, context=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36",
        "authorization": "Bearer " + api_key,
    }
    response = None
    try:
        response = session.post(url, headers=headers, data=data)
        logerror(response, context)
        response = json.loads(
            response.content, object_hook=lambda d: SimpleNamespace(**d)
        )
    except Exception as e:
        if hasattr(response, "status_code"):
            if response.status_code >= 300:
                ui_print(
                    "[realdebrid] error: (json exception): "
                    + str(e)
                    + (" Context: " + str(context) if context else ""),
                    debug=ui_settings.debug,
                )
        else:
            ui_print(
                "[realdebrid] error: (json exception): "
                + str(e)
                + (" Context: " + str(context) if context else ""),
                debug=ui_settings.debug,
            )
        response = None
    return response


# Delete Function
def delete(url, context=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36",
        "authorization": "Bearer " + api_key,
    }
    try:
        resp = requests.delete(url, headers=headers)
        if resp.status_code >= 300:
            logerror(resp, context)
        # time.sleep(1)
    except Exception as e:
        ui_print(
            "[realdebrid] error: (delete exception): "
            + str(e)
            + (" Context: " + str(context) if context else ""),
            debug=ui_settings.debug,
        )
        None
    return None


def _post_download_cleanup(element):
    """Remove element from downloading list and refresh library services."""
    import debrid as db

    download_id = element.query()
    if hasattr(element, "version"):
        download_id += " [" + element.version.name + "]"
    if download_id in db.downloading:
        db.downloading.remove(download_id)
    try:
        from content.services import jellyfin

        jellyfin.library.refresh(element)
    except Exception as e:
        ui_print(
            f"[realdebrid] could not refresh jellyfin libraries: {str(e)}",
            debug=ui_settings.debug,
        )
    try:
        from content.services import seerr

        seerr.library.refresh(element)
    except Exception as e:
        ui_print(
            f"[realdebrid] could not mark seerr request as available: {str(e)}",
            debug=ui_settings.debug,
        )


# (required) Download Function.
def download(element, query="", force=False):
    import time

    cached = element.Releases
    if query == "":
        query = element.deviation()

    # For episodes/seasons, also accept full season releases even if they don't match episode pattern
    alternative_query = None
    if hasattr(element, "type") and element.type == "episode":
        # For episodes, also try to match season-level releases
        # Extract season number from episode pattern and create a season pattern
        parent_index = getattr(element, "parentIndex", None)
        if parent_index is not None:
            # Try to match releases with just the season number (S01, S01.COMPLETE, etc.)
            alternative_query = f"S{parent_index:02d}"

    for release in cached[:]:
        is_http_release = hasattr(release, "type") and release.type == "http"

        # Now check if release matches query OR alternative query OR force OR is cached
        matches_primary = regex.match(query, release.title, regex.I)

        # For HTTP releases, SKIP alternative_query matching
        # HTTP season packs are single files and shouldn't match individual episode queries
        # Only torrents (multi-file season packs) should match via alternative_query
        if is_http_release:
            matches_alternative = False
        else:
            matches_alternative = (
                alternative_query and alternative_query.lower() in release.title.lower()
            )

        is_cached = hasattr(release, "cached") and release.cached

        if matches_primary or matches_alternative or force or is_cached:

            release.size = 0

            if is_http_release:
                ui_print(
                    "[realdebrid] downloading http release: " + release.title,
                    ui_settings.debug,
                )
                if release.download and len(release.download) > 0:
                    download_success = downloader.download_from_realdebrid(
                        release, element
                    )
                    if download_success:
                        ui_print("[realdebrid] download complete (http)")
                        _post_download_cleanup(element)
                        return True
                continue

            # Check if files are available, if not we need to add magnet to get file list
            if not release.files or all(
                not hasattr(v, "files") or len(v.files) == 0 for v in release.files
            ):
                ui_print(
                    "[realdebrid] no file info available (nodownloadlinks enabled), adding magnet to RD...",
                    ui_settings.debug,
                )
                try:
                    context = (
                        "release: '"
                        + str(release.title)
                        + "' | item: '"
                        + str(element.query())
                        + "'"
                    )
                    magnet_candidate = ""
                    if (
                        hasattr(release, "download")
                        and release.download
                        and len(release.download) > 0
                    ):
                        magnet_candidate = str(release.download[0])

                    if not magnet_candidate.startswith("magnet:"):
                        ui_print(
                            "[realdebrid] error: invalid download link (not magnet): "
                            + str(magnet_candidate)
                            + " | release: "
                            + release.title,
                            ui_settings.debug,
                        )
                        continue

                    try:
                        response = post(
                            "https://api.real-debrid.com/rest/1.0/torrents/addMagnet",
                            {"magnet": magnet_candidate},
                            context=context,
                        )
                    except Exception as add_magnet_error:
                        ui_print(
                            "[realdebrid] error adding magnet (will try next release): "
                            + str(add_magnet_error),
                            ui_settings.debug,
                        )
                        continue

                    if (
                        not response
                        or hasattr(response, "error")
                        or not hasattr(response, "id")
                    ):
                        ui_print(
                            "[realdebrid] error adding magnet: "
                            + (
                                response.error
                                if response and hasattr(response, "error")
                                else "unknown error"
                            ),
                            ui_settings.debug,
                        )
                        continue

                    torrent_id = str(response.id)
                    ui_print(
                        "[realdebrid] magnet added, torrent_id: " + torrent_id,
                        ui_settings.debug,
                    )

                    time.sleep(2)
                    response = get(
                        "https://api.real-debrid.com/rest/1.0/torrents/info/"
                        + torrent_id,
                        context=context,
                    )
                    ui_print(
                        "[realdebrid] torrent status: " + response.status,
                        ui_settings.debug,
                    )

                    if hasattr(response, "files") and len(response.files) > 0:
                        video_extensions = [
                            ".mkv",
                            ".mp4",
                            ".avi",
                            ".mov",
                            ".flv",
                            ".wmv",
                            ".webm",
                            ".m4v",
                            ".mpg",
                            ".mpeg",
                            ".3gp",
                            ".ogv",
                            ".ts",
                            ".m2ts",
                            ".mts",
                            ".m2v",
                            ".m4p",
                            ".mxf",
                            ".asf",
                            ".rm",
                            ".rmvb",
                            ".vob",
                            ".f4v",
                            ".divx",
                        ]
                        file_ids = [
                            str(f.id)
                            for f in response.files
                            if any(
                                getattr(
                                    f,
                                    "path",
                                    getattr(
                                        f,
                                        "filename",
                                        getattr(f, "name", ""),
                                    ),
                                )
                                .lower()
                                .endswith(ext)
                                for ext in video_extensions
                            )
                        ]

                        if not file_ids:
                            ui_print(
                                "[realdebrid] warning: no video files found, selecting all files",
                                ui_settings.debug,
                            )
                            file_ids = [str(f.id) for f in response.files]

                        ui_print(
                            "[realdebrid] selecting "
                            + str(len(file_ids))
                            + " video files...",
                            ui_settings.debug,
                        )
                        post(
                            "https://api.real-debrid.com/rest/1.0/torrents/selectFiles/"
                            + torrent_id,
                            {"files": ",".join(file_ids)},
                            context=context,
                        )

                        max_polls = 5
                        final_status = "unknown"
                        for poll in range(max_polls):
                            time.sleep(2)
                            response = get(
                                "https://api.real-debrid.com/rest/1.0/torrents/info/"
                                + torrent_id,
                                context=context,
                            )
                            final_status = response.status
                            if response.status == "downloaded" or (
                                hasattr(response, "links") and len(response.links) > 0
                            ):
                                break
                        ui_print(
                            "[realdebrid] torrent status after polling: "
                            + final_status,
                            ui_settings.debug,
                        )

                        unrestricted_links = []
                        filenames = []

                        if hasattr(response, "links") and len(response.links) > 0:
                            ui_print(
                                "[realdebrid] getting unrestricted links for "
                                + str(len(response.links))
                                + " video files...",
                                ui_settings.debug,
                            )

                            selected_file_names = []
                            if hasattr(response, "files"):
                                for f in response.files:
                                    is_selected = False
                                    if hasattr(f, "selected"):
                                        is_selected = (
                                            f.selected == 1
                                            or f.selected is True
                                            or f.selected
                                        )
                                    if is_selected:
                                        filename = getattr(
                                            f,
                                            "path",
                                            getattr(
                                                f,
                                                "filename",
                                                getattr(f, "name", ""),
                                            ),
                                        )
                                        if "/" in filename:
                                            filename = filename.split("/")[-1]
                                        selected_file_names.append(filename)

                            for idx, link in enumerate(response.links):
                                try:
                                    unres_response = post(
                                        "https://api.real-debrid.com/rest/1.0/unrestrict/link",
                                        {"link": link},
                                        context=context,
                                    )
                                    if hasattr(unres_response, "download"):
                                        unrestricted_links.append(
                                            unres_response.download
                                        )
                                        if (
                                            idx < len(selected_file_names)
                                            and selected_file_names[idx]
                                        ):
                                            filename = selected_file_names[idx]
                                        elif hasattr(unres_response, "filename"):
                                            filename = unres_response.filename
                                        else:
                                            filename = (
                                                release.title + "_file_" + str(idx)
                                            )
                                        filenames.append(filename)
                                except Exception as e:
                                    ui_print(
                                        "[realdebrid] error getting unrestricted link: "
                                        + str(e),
                                        debug=True,
                                    )
                                    continue

                            if len(unrestricted_links) > 0:
                                release.download = unrestricted_links
                                release.filenames = filenames
                                ui_print(
                                    "[realdebrid] downloading from cached RD torrent: "
                                    + release.title
                                )
                                download_success = downloader.download_from_realdebrid(
                                    release, element
                                )
                                if download_success:
                                    ui_print("[realdebrid] download complete (torrent)")
                                    _post_download_cleanup(element)
                                    return True
                        else:
                            ui_print(
                                "[realdebrid] no links available yet, status: "
                                + response.status,
                                ui_settings.debug,
                            )
                            ui_print(
                                "[realdebrid] deleting torrent (cannot use): "
                                + torrent_id,
                                ui_settings.debug,
                            )
                            delete(
                                "https://api.real-debrid.com/rest/1.0/torrents/delete/"
                                + torrent_id,
                                context=context,
                            )
                except Exception as e:
                    ui_print(
                        "[realdebrid] error processing torrent: " + str(e),
                        ui_settings.debug,
                    )
                    continue

            ui_print(
                "[realdebrid] error: no streamable version could be selected for release: "
                + release.title
            )
            return False
        else:
            ui_print(
                '[realdebrid] error: rejecting release: "'
                + release.title
                + '" because it doesnt match the allowed deviation',
                ui_settings.debug,
            )
            continue  # Skip to next release instead of stopping
    return False


# (required) Check Function
def check(element, force=False):
    http_count = 0
    ignored_count = 0
    for release in element.Releases[:]:
        # Skip hash checking for HTTP type releases (e.g., from AIOStreams)
        if hasattr(release, "type") and release.type == "http":
            release.cached += ["RD"]
            http_count += 1
            continue

        release_hash = getattr(release, "hash", "")
        if isinstance(release_hash, str) and len(release_hash) == 40:
            release.cached += ["RD"]
            release.files = []
        else:
            ui_print(
                "[realdebrid] error (missing torrent hash): ignoring release '"
                + release.title
                + "' ",
                ui_settings.debug,
            )
            element.Releases.remove(release)
            ignored_count += 1

    # Sort releases by size to prioritize best quality
    element.Releases.sort(key=lambda x: getattr(x, "size", 0), reverse=True)
    ui_print(
        "[realdebrid] marked "
        + str(len(element.Releases))
        + " releases as cached (scraper pre-verified)"
        + (
            " ["
            + str(http_count)
            + " http, "
            + str(len(element.Releases) - http_count)
            + " torrent]"
            if http_count
            else ""
        )
        + (" [" + str(ignored_count) + " ignored]" if ignored_count else ""),
        ui_settings.debug,
    )
