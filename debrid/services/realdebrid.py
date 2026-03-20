# import modules
import json
from types import SimpleNamespace

import regex
import requests

import downloader
from ui.ui_print import ui_print, ui_settings

# Try to import rd_downloader for existing torrents
try:
    has_rd_downloader = True
except Exception:
    has_rd_downloader = False
    ui_print("[realdebrid] rd_downloader module not available", ui_settings.debug)

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


# (required) Download Function.
def download(element, stream=True, query="", force=False):
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
        # Detect HTTP type releases FIRST - before any matching logic
        is_http_release = False
        if release.download and len(release.download) > 0:
            download_str = str(release.download[0])
            # Check both type attribute AND download URL format
            if (
                (hasattr(release, "type") and release.type == "http")
                or download_str.startswith("http://")
                or download_str.startswith("https://")
            ):
                is_http_release = True
                release.type = "http"

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
            if stream:
                release.size = 0

                # Debug: Log release attributes for HTTP detection
                release_type = getattr(release, "type", None)
                download_val = getattr(release, "download", None)
                download_preview = (
                    str(download_val[0])[:100]
                    if download_val and len(download_val) > 0
                    else "None"
                )
                ui_print(
                    "[realdebrid] debug: checking release: "
                    + release.title
                    + " | type="
                    + str(release_type)
                    + " | is_http: "
                    + str(is_http_release)
                    + " | download[0]: "
                    + download_preview,
                    ui_settings.debug,
                )

                # Handle HTTP type releases (e.g., from AIOStreams) - direct download links
                # Do this BEFORE any magnet/file processing
                if is_http_release:
                    ui_print(
                        "[realdebrid] processing http stream link: " + release.title,
                        ui_settings.debug,
                    )
                    if release.download and len(release.download) > 0:
                        http_url = release.download[0]
                        ui_print(
                            "[realdebrid] http download url: " + http_url[:100] + "...",
                            ui_settings.debug,
                        )
                        ui_print(
                            "[realdebrid] http release ready for download: "
                            + release.title,
                            ui_settings.debug,
                        )
                        download_success = downloader.download_from_realdebrid(
                            release, element
                        )
                        if download_success:
                            ui_print(
                                "[realdebrid] successfully downloaded file from http stream"
                            )
                            # Remove from downloading list
                            import debrid as db

                            download_id = element.query()
                            if hasattr(element, "version"):
                                download_id += " [" + element.version.name + "]"
                            ui_print(
                                f'[realdebrid] debug: checking if "{download_id}" is in downloading list (len={len(db.downloading)}): {db.downloading}',
                                ui_settings.debug,
                            )
                            if download_id in db.downloading:
                                db.downloading.remove(download_id)
                                ui_print(
                                    f"[realdebrid] removed from downloading list: {download_id}"
                                )
                            else:
                                ui_print(
                                    f'[realdebrid] warning: download_id "{download_id}" not found in downloading list: {db.downloading}'
                                )
                            # Trigger Jellyfin library refresh after successful download
                            try:
                                from content.services import jellyfin

                                jellyfin.library.refresh(element)
                            except Exception as e:
                                ui_print(
                                    f"[realdebrid] could not refresh jellyfin libraries: {str(e)}",
                                    debug=True,
                                )
                            # Mark Seerr request as available after successful download
                            try:
                                from content.services import seerr

                                seerr.library.refresh(element)
                            except Exception as e:
                                ui_print(
                                    f"[realdebrid] could not mark seerr request as available: {str(e)}",
                                    debug=True,
                                )
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
                    # Add magnet to get file information
                    try:
                        context = (
                            "release: '"
                            + str(release.title)
                            + "' | item: '"
                            + str(element.query())
                            + "'"
                        )
                        # Validate the download link before attempting to add as magnet
                        magnet_candidate = ""
                        if (
                            hasattr(release, "download")
                            and release.download
                            and len(release.download) > 0
                        ):
                            magnet_candidate = str(release.download[0])

                        # If this is an HTTP URL, process as HTTP stream instead of adding magnet
                        if magnet_candidate.startswith(
                            "http://"
                        ) or magnet_candidate.startswith("https://"):
                            # Check deviation before downloading HTTP stream
                            if not (matches_primary or matches_alternative or force):
                                ui_print(
                                    '[realdebrid] error: rejecting http release (no file info): "'
                                    + release.title
                                    + '" because it doesnt match the allowed deviation',
                                    ui_settings.debug,
                                )
                                continue  # Skip to next release

                            ui_print(
                                "[realdebrid] warning: download entry looks like an HTTP URL in addMagnet path, processing as HTTP instead: "
                                + release.title,
                                ui_settings.debug,
                            )
                            release.type = "http"
                            download_success = downloader.download_from_realdebrid(
                                release, element
                            )
                            if download_success:
                                ui_print(
                                    "[realdebrid] successfully downloaded file from http stream"
                                )
                                # Remove from downloading list
                                import debrid as db

                                download_id = element.query()
                                if hasattr(element, "version"):
                                    download_id += " [" + element.version.name + "]"
                                if download_id in db.downloading:
                                    db.downloading.remove(download_id)
                                    ui_print(
                                        f"[realdebrid] removed from downloading list: {download_id}",
                                        debug=True,
                                    )
                                try:
                                    from content.services import jellyfin

                                    jellyfin.library.refresh(element)
                                except Exception as e:
                                    ui_print(
                                        f"[realdebrid] could not refresh jellyfin libraries: {str(e)}",
                                        debug=True,
                                    )
                                try:
                                    from content.services import seerr

                                    seerr.library.refresh(element)
                                except Exception as e:
                                    ui_print(
                                        f"[realdebrid] could not mark seerr request as available: {str(e)}",
                                        debug=True,
                                    )
                                return True
                            continue

                        # Only attempt to add if it looks like a magnet
                        try:
                            if magnet_candidate.startswith("magnet:"):
                                try:
                                    response = post(
                                        "https://api.real-debrid.com/rest/1.0/torrents/addMagnet",
                                        {"magnet": magnet_candidate},
                                        context=context,
                                    )
                                except Exception as add_magnet_error:
                                    ui_print(
                                        f"[realdebrid] error adding magnet (will try next release): {str(add_magnet_error)}",
                                        ui_settings.debug,
                                    )
                                    continue  # Try next release instead of failing completely

                                # Check if response has an error or missing id
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
                            else:
                                ui_print(
                                    "[realdebrid] error: invalid download link (not magnet or http): "
                                    + str(magnet_candidate)
                                    + " | release: "
                                    + release.title,
                                    ui_settings.debug,
                                )
                                continue

                            torrent_id = str(response.id)
                            ui_print(
                                "[realdebrid] magnet added, torrent_id: " + torrent_id,
                                ui_settings.debug,
                            )

                            # Get torrent info to see available files
                            time.sleep(2)  # Wait for RD to process
                            response = get(
                                "https://api.real-debrid.com/rest/1.0/torrents/info/"
                                + torrent_id,
                                context=context,
                            )
                            ui_print(
                                "[realdebrid] torrent status: " + response.status,
                                ui_settings.debug,
                            )

                            # Select only video files in the torrent (avoid .rar, .exe, etc.)
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
                                    # Fallback: select all files if no video files found
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

                                # Poll for torrent to become ready (cached torrents need a moment)
                                max_polls = 5
                                for poll in range(max_polls):
                                    time.sleep(2)
                                    response = get(
                                        "https://api.real-debrid.com/rest/1.0/torrents/info/"
                                        + torrent_id,
                                        context=context,
                                    )
                                    ui_print(
                                        "[realdebrid] updated status: "
                                        + response.status
                                        + f" (poll {poll + 1}/{max_polls})",
                                        ui_settings.debug,
                                    )
                                    if response.status == "downloaded" or (
                                        hasattr(response, "links")
                                        and len(response.links) > 0
                                    ):
                                        break

                                # Get unrestricted links - use response.links which contains links for all selected files
                                unrestricted_links = []
                                filenames = []

                                if (
                                    hasattr(response, "links")
                                    and len(response.links) > 0
                                ):
                                    ui_print(
                                        f"[realdebrid] getting unrestricted links for {len(response.links)} video files...",
                                        ui_settings.debug,
                                    )

                                    # Get corresponding filenames from the files that were selected
                                    selected_file_names = []
                                    if hasattr(response, "files"):
                                        # Get filenames for selected files (selected == 1 or selected == True)
                                        for f in response.files:
                                            is_selected = False
                                            if hasattr(f, "selected"):
                                                # Handle both integer (1) and boolean (True) values
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
                                                # Extract just the filename from path if needed
                                                if "/" in filename:
                                                    filename = filename.split("/")[-1]
                                                selected_file_names.append(filename)

                                    # Get unrestricted download links for each link
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
                                                # Use filename from our selected_file_names list, or from unrestrict response, or fallback
                                                if (
                                                    idx < len(selected_file_names)
                                                    and selected_file_names[idx]
                                                ):
                                                    filename = selected_file_names[idx]
                                                elif hasattr(
                                                    unres_response, "filename"
                                                ):
                                                    filename = unres_response.filename
                                                else:
                                                    filename = (
                                                        release.title
                                                        + "_file_"
                                                        + str(idx)
                                                    )
                                                filenames.append(filename)
                                                ui_print(
                                                    f"[realdebrid] debug: got link for video file: {filename}",
                                                    debug=True,
                                                )
                                        except Exception as e:
                                            ui_print(
                                                f"[realdebrid] error getting unrestricted link: {str(e)}",
                                                debug=True,
                                            )
                                            continue

                                    if len(unrestricted_links) > 0:
                                        release.download = unrestricted_links
                                        release.filenames = (
                                            filenames  # Store actual filenames
                                        )
                                        ui_print(
                                            "[realdebrid] downloading from cached RD torrent: "
                                            + release.title
                                        )
                                        ui_print(
                                            f"[realdebrid] debug: filenames from RD unrestrict: {filenames}",
                                            debug=True,
                                        )
                                        ui_print(
                                            f"[realdebrid] debug: download links: {[link[:80] + '...' for link in unrestricted_links]}",
                                            debug=True,
                                        )
                                        download_success = (
                                            downloader.download_from_realdebrid(
                                                release, element
                                            )
                                        )
                                        if download_success:
                                            ui_print(
                                                "[realdebrid] successfully downloaded file to local storage"
                                            )
                                            # Trigger Jellyfin library refresh after successful download
                                            try:
                                                from content.services import jellyfin

                                                jellyfin.library.refresh(element)
                                            except Exception as e:
                                                ui_print(
                                                    f"[realdebrid] could not refresh jellyfin libraries: {str(e)}",
                                                    debug=True,
                                                )
                                            # Mark Seerr request as available after successful download
                                            try:
                                                from content.services import seerr

                                                seerr.library.refresh(element)
                                            except Exception as e:
                                                ui_print(
                                                    f"[realdebrid] could not mark seerr request as available: {str(e)}",
                                                    debug=True,
                                                )
                                            return True
                                else:
                                    # Torrent is still downloading/queued - check if we should keep it as uncached
                                    ui_print(
                                        "[realdebrid] no links available yet, status: "
                                        + response.status,
                                        ui_settings.debug,
                                    )

                                    if response.status in [
                                        "queued",
                                        "magnet_conversion",
                                        "downloading",
                                        "uploading",
                                    ]:
                                        # Check if element allows uncached downloads
                                        if hasattr(element, "version"):
                                            debrid_uncached = True
                                            for i, rule in enumerate(
                                                element.version.rules
                                            ):
                                                if (
                                                    (rule[0] == "cache status")
                                                    and (
                                                        rule[1] == "requirement"
                                                        or rule[1] == "preference"
                                                    )
                                                    and (rule[2] == "cached")
                                                ):
                                                    debrid_uncached = False
                                            if debrid_uncached:
                                                # Keep this torrent and mark as uncached download in progress
                                                import debrid as db

                                                download_id = (
                                                    element.query()
                                                    + " ["
                                                    + element.version.name
                                                    + "]"
                                                )
                                                if download_id not in db.downloading:
                                                    db.downloading.append(download_id)
                                                ui_print(
                                                    "[realdebrid] keeping uncached torrent (status: "
                                                    + response.status
                                                    + ") - will retry later",
                                                    ui_settings.debug,
                                                )
                                                return True

                                    # Delete torrent if we can't use it (either wrong status or cached-only requirement)
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
                            import traceback

                            ui_print(
                                "[realdebrid] traceback: " + traceback.format_exc(),
                                ui_settings.debug,
                            )
                            continue  # Skip to next release on error
                    except Exception as outer_e:
                        ui_print(
                            "[realdebrid] error in outer magnet processing: "
                            + str(outer_e),
                            ui_settings.debug,
                        )
                        continue

                ui_print(
                    "[realdebrid] error: no streamable version could be selected for release: "
                    + release.title
                )
                return False
            else:
                # For uncached downloads, also check if release matches deviation pattern
                if not (matches_primary or matches_alternative or force):
                    ui_print(
                        '[realdebrid] error: rejecting uncached release: "'
                        + release.title
                        + '" because it doesnt match the allowed deviation',
                        ui_settings.debug,
                    )
                    continue  # Skip to next release

                try:
                    context = (
                        "release: '"
                        + str(release.title)
                        + "' | item: '"
                        + str(element.query())
                        + "'"
                    )
                    # Validate before adding magnet
                    magnet_candidate = ""
                    if (
                        hasattr(release, "download")
                        and release.download
                        and len(release.download) > 0
                    ):
                        magnet_candidate = str(release.download[0])

                    if magnet_candidate.startswith(
                        "http://"
                    ) or magnet_candidate.startswith("https://"):
                        # Check deviation before downloading HTTP stream
                        if not (matches_primary or matches_alternative or force):
                            ui_print(
                                '[realdebrid] error: rejecting uncached http release: "'
                                + release.title
                                + '" because it doesnt match the allowed deviation',
                                ui_settings.debug,
                            )
                            continue  # Skip to next release

                        ui_print(
                            "[realdebrid] warning: download entry looks like an HTTP URL in addMagnet path, processing as HTTP instead: "
                            + release.title,
                            ui_settings.debug,
                        )
                        release.type = "http"
                        download_success = downloader.download_from_realdebrid(
                            release, element
                        )
                        if download_success:
                            ui_print(
                                "[realdebrid] successfully downloaded file from http stream"
                            )
                            # Remove from downloading list
                            import debrid as db

                            if hasattr(element, "version"):
                                download_id = (
                                    element.query() + " [" + element.version.name + "]"
                                )
                                ui_print(
                                    f'[realdebrid] debug: checking if "{download_id}" is in downloading list (len={len(db.downloading)}): {db.downloading}',
                                    ui_settings.debug,
                                )
                                if download_id in db.downloading:
                                    db.downloading.remove(download_id)
                                    ui_print(
                                        f"[realdebrid] removed from downloading list: {download_id}"
                                    )
                                else:
                                    ui_print(
                                        f'[realdebrid] warning: download_id "{download_id}" not found in downloading list: {db.downloading}'
                                    )
                            try:
                                from content.services import jellyfin

                                jellyfin.library.refresh(element)
                            except Exception as e:
                                ui_print(
                                    f"[realdebrid] could not refresh jellyfin libraries: {str(e)}",
                                    debug=True,
                                )
                            try:
                                from content.services import seerr

                                seerr.library.refresh(element)
                            except Exception as e:
                                ui_print(
                                    f"[realdebrid] could not mark seerr request as available: {str(e)}",
                                    debug=True,
                                )
                            return True
                        continue

                    if magnet_candidate.startswith("magnet:"):
                        response = post(
                            "https://api.real-debrid.com/rest/1.0/torrents/addMagnet",
                            {"magnet": magnet_candidate},
                            context=context,
                        )
                    else:
                        ui_print(
                            "[realdebrid] error: invalid download link (not magnet or http): "
                            + str(magnet_candidate)
                            + " | release: "
                            + release.title,
                            ui_settings.debug,
                        )
                        continue
                    time.sleep(0.1)
                    post(
                        "https://api.real-debrid.com/rest/1.0/torrents/selectFiles/"
                        + str(response.id),
                        {"files": "all"},
                        context=context,
                    )
                    ui_print("[realdebrid] adding uncached release: " + release.title)
                    return True
                except Exception:
                    continue
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
    for release in element.Releases[:]:
        # Skip hash checking for HTTP type releases (e.g., from AIOStreams)
        if hasattr(release, "type") and release.type == "http":
            ui_print(
                "[realdebrid] skipping hash check for http release: '"
                + release.title
                + "' (will process directly)",
                ui_settings.debug,
            )
            release.cached += ["RD"]
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

    # Sort releases by size to prioritize best quality
    element.Releases.sort(key=lambda x: getattr(x, "size", 0), reverse=True)
    ui_print(
        "[realdebrid] marked "
        + str(len(element.Releases))
        + " releases as cached (scraper pre-verified)",
        ui_settings.debug,
    )


# Diagnostic: get basic account info (useful to debug 403 permissions)
def account_info():
    try:
        response = get("https://api.real-debrid.com/rest/1.0/user")
        if response is None:
            ui_print(
                "[realdebrid] error: unable to fetch account info", ui_settings.debug
            )
            return None
        ui_print(
            "[realdebrid] account info: " + str(response.__dict__), ui_settings.debug
        )
        return response
    except Exception as e:
        ui_print(
            "[realdebrid] error: fetching account info: " + str(e), ui_settings.debug
        )
        return None


# Diagnostic: list torrents (helps verify that RD accepted an uncached torrent and its download status)
def torrents_list(limit=50):
    try:
        response = get(
            "https://api.real-debrid.com/rest/1.0/torrents?limit=" + str(limit),
            context="torrents_list",
        )
        if response is None:
            ui_print(
                "[realdebrid] error: unable to fetch torrents list", ui_settings.debug
            )
            return None
        # Response is a list of torrent objects
        try:
            summary = [
                {
                    "id": t.id,
                    "status": t.status,
                    "filename": getattr(t, "filename", None),
                    "files": (
                        len(getattr(t, "files", [])) if hasattr(t, "files") else None
                    ),
                }
                for t in response
            ]
        except Exception:
            summary = str(response)
        ui_print("[realdebrid] torrents: " + str(summary), ui_settings.debug)
        return response
    except Exception as e:
        ui_print(
            "[realdebrid] error: fetching torrents list: " + str(e), ui_settings.debug
        )
        return None
