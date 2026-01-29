# import modules
import json
from types import SimpleNamespace

import regex
import requests

import downloader
import releases
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


# Object classes
class file:
    def __init__(self, id, name, size, wanted_list, unwanted_list):
        self.id = id
        self.name = name
        self.size = size / 1000000000
        self.match = ""
        wanted = False
        unwanted = False
        for key, wanted_pattern in wanted_list:
            if wanted_pattern.search(self.name):
                wanted = True
                self.match = key
                break

        if not wanted:
            for key, unwanted_pattern in unwanted_list:
                if (
                    unwanted_pattern.search(self.name)
                    or self.name.endswith(".exe")
                    or self.name.endswith(".txt")
                ):
                    unwanted = True
                    break

        self.wanted = wanted
        self.unwanted = unwanted

    def __eq__(self, other):
        return self.id == other.id


class version:
    def __init__(self, files):
        self.files = files
        self.needed = 0
        self.wanted = 0
        self.unwanted = 0
        self.size = 0
        for file in self.files:
            self.size += file.size
            if file.wanted:
                self.wanted += 1
            if file.unwanted:
                self.unwanted += 1


# (required) Download Function.
def download(element, stream=True, query="", force=False):
    cached = element.Releases
    if query == "":
        query = element.deviation()
    wanted = [query]
    if not isinstance(element, releases.release):
        wanted = element.files()

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
        # if release matches query OR alternative query OR force OR is cached
        matches_primary = regex.match(query, release.title, regex.I)
        matches_alternative = (
            alternative_query and alternative_query.lower() in release.title.lower()
        )
        is_cached = hasattr(release, "cached") and release.cached

        if matches_primary or matches_alternative or force or is_cached:
            if stream:
                release.size = 0

                # Detect HTTP type releases FIRST - before any processing
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
                            # Mark Jellyseerr request as available after successful download
                            try:
                                from content.services import jellyseerr

                                jellyseerr.library.refresh(element)
                            except Exception as e:
                                ui_print(
                                    f"[realdebrid] could not mark jellyseerr request as available: {str(e)}",
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
                                    from content.services import jellyseerr

                                    jellyseerr.library.refresh(element)
                                except Exception as e:
                                    ui_print(
                                        f"[realdebrid] could not mark jellyseerr request as available: {str(e)}",
                                        debug=True,
                                    )
                                return True
                            continue

                        # Only attempt to add if it looks like a magnet
                        try:
                            if magnet_candidate.startswith("magnet:"):
                                response = post(
                                    "https://api.real-debrid.com/rest/1.0/torrents/addMagnet",
                                    {"magnet": magnet_candidate},
                                    context=context,
                                )
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
                            import time

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
                                        getattr(f, "filename", getattr(f, "name", ""))
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

                                # Wait a bit more and get updated info
                                time.sleep(2)
                                response = get(
                                    "https://api.real-debrid.com/rest/1.0/torrents/info/"
                                    + torrent_id,
                                    context=context,
                                )
                                ui_print(
                                    "[realdebrid] updated status: " + response.status,
                                    ui_settings.debug,
                                )

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
                                            # Mark Jellyseerr request as available after successful download
                                            try:
                                                from content.services import jellyseerr

                                                jellyseerr.library.refresh(element)
                                            except Exception as e:
                                                ui_print(
                                                    f"[realdebrid] could not mark jellyseerr request as available: {str(e)}",
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

                for version in release.files:
                    if hasattr(version, "files"):
                        if (
                            len(version.files) > 0
                            and version.wanted > len(wanted) / 2
                            or force
                        ):
                            cached_ids = []
                            for file in version.files:
                                cached_ids += [file.id]
                            # post magnet to real debrid
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
                                    if not (
                                        matches_primary or matches_alternative or force
                                    ):
                                        ui_print(
                                            '[realdebrid] error: rejecting http release: "'
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
                                    download_success = (
                                        downloader.download_from_realdebrid(
                                            release, element
                                        )
                                    )
                                    if download_success:
                                        ui_print(
                                            "[realdebrid] successfully downloaded file from http stream"
                                        )
                                        # Remove from downloading list
                                        import debrid as db

                                        if hasattr(element, "version"):
                                            download_id = (
                                                element.query()
                                                + " ["
                                                + element.version.name
                                                + "]"
                                            )
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
                                            from content.services import jellyseerr

                                            jellyseerr.library.refresh(element)
                                        except Exception as e:
                                            ui_print(
                                                f"[realdebrid] could not mark jellyseerr request as available: {str(e)}",
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
                                    torrent_id = str(response.id)
                                else:
                                    ui_print(
                                        "[realdebrid] error: invalid download link (not magnet or http): "
                                        + str(magnet_candidate)
                                        + " | release: "
                                        + release.title,
                                        ui_settings.debug,
                                    )
                                    continue
                            except Exception as e:
                                ui_print(
                                    "[realdebrid] error: could not add magnet for release: "
                                    + release.title
                                    + " ("
                                    + str(e)
                                    + ")",
                                    ui_settings.debug,
                                )
                                continue
                            response = post(
                                "https://api.real-debrid.com/rest/1.0/torrents/selectFiles/"
                                + torrent_id,
                                {"files": str(",".join(cached_ids))},
                                context=context,
                            )
                            response = get(
                                "https://api.real-debrid.com/rest/1.0/torrents/info/"
                                + torrent_id,
                                context=context,
                            )
                            actual_title = ""
                            if len(response.links) == len(cached_ids):
                                actual_title = response.filename
                                release.download = response.links
                            else:
                                if response.status in [
                                    "queued",
                                    "magnet_convesion",
                                    "downloading",
                                    "uploading",
                                ]:
                                    if hasattr(element, "version"):
                                        debrid_uncached = True
                                        for i, rule in enumerate(element.version.rules):
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
                                            import debrid as db

                                            release.files = version.files
                                            db.downloading += [
                                                element.query()
                                                + " ["
                                                + element.version.name
                                                + "]"
                                            ]
                                            ui_print(
                                                "[realdebrid] adding uncached release: "
                                                + release.title
                                            )
                                            return True
                                else:
                                    ui_print(
                                        "[realdebrid] error: selecting this cached file combination returned a .rar archive - trying a different file combination.",
                                        ui_settings.debug,
                                    )
                                    delete(
                                        "https://api.real-debrid.com/rest/1.0/torrents/delete/"
                                        + torrent_id,
                                        context=context,
                                    )
                                    continue
                            if len(release.download) > 0:
                                # Get unrestricted download links
                                unrestricted_links = []
                                for link in release.download:
                                    try:
                                        response = post(
                                            "https://api.real-debrid.com/rest/1.0/unrestrict/link",
                                            {"link": link},
                                            context=context,
                                        )
                                        if hasattr(response, "download"):
                                            unrestricted_links.append(response.download)
                                    except Exception:
                                        break

                                # Update release with unrestricted links
                                if len(unrestricted_links) > 0:
                                    release.download = unrestricted_links

                                release.files = version.files
                                ui_print(
                                    "[realdebrid] adding cached release: "
                                    + release.title
                                )
                                if not actual_title == "":
                                    release.title = actual_title

                                # Download the best file locally
                                try:
                                    ui_print(
                                        "[realdebrid] initiating local download of best quality file..."
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
                                        # Remove from downloading list
                                        import debrid as db

                                        if hasattr(element, "version"):
                                            download_id = (
                                                element.query()
                                                + " ["
                                                + element.version.name
                                                + "]"
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
                                    else:
                                        ui_print(
                                            "[realdebrid] warning: download to local storage failed, but release was added"
                                        )
                                except Exception as e:
                                    ui_print(
                                        f"[realdebrid] error during download: {str(e)}",
                                        ui_settings.debug,
                                    )

                                return True
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
                                from content.services import jellyseerr

                                jellyseerr.library.refresh(element)
                            except Exception as e:
                                ui_print(
                                    f"[realdebrid] could not mark jellyseerr request as available: {str(e)}",
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
    if force:
        wanted = [".*"]
    else:
        wanted = element.files()
    unwanted = releases.sort.unwanted
    wanted_patterns = list(
        zip(
            wanted,
            [regex.compile(r"(" + key + ")", regex.IGNORECASE) for key in wanted],
        )
    )
    unwanted_patterns = list(
        zip(
            unwanted,
            [regex.compile(r"(" + key + ")", regex.IGNORECASE) for key in unwanted],
        )
    )

    hashes = []
    for release in element.Releases[:]:
        # Skip hash checking for HTTP type releases (e.g., from AIOStreams)
        if hasattr(release, "type") and release.type == "http":
            ui_print(
                "[realdebrid] skipping hash check for http release: '"
                + release.title
                + "' (will process directly)",
                ui_settings.debug,
            )
            continue

        if len(release.hash) == 40:
            hashes += [release.hash]
        else:
            ui_print(
                "[realdebrid] error (missing torrent hash): ignoring release '"
                + release.title
                + "' ",
                ui_settings.debug,
            )
            element.Releases.remove(release)
    if len(hashes) > 0:
        response = get(
            "https://api.real-debrid.com/rest/1.0/torrents/instantAvailability/"
            + "/".join(hashes),
            context=element.query(),
        )
        ui_print(
            "[realdebrid] checking and sorting all release files ...", ui_settings.debug
        )
        for release in element.Releases:
            release.files = []
            release_hash = release.hash.lower()
            if hasattr(response, release_hash):
                response_attr = getattr(response, release_hash)
                if hasattr(response_attr, "rd"):
                    rd_attr = response_attr.rd
                    if len(rd_attr) > 0:
                        for cashed_version in rd_attr:
                            version_files = []
                            for file_ in cashed_version.__dict__:
                                file_attr = getattr(cashed_version, file_)
                                debrid_file = file(
                                    file_,
                                    file_attr.filename,
                                    file_attr.filesize,
                                    wanted_patterns,
                                    unwanted_patterns,
                                )
                                version_files.append(debrid_file)
                            release.files += [
                                version(version_files),
                            ]
                        # select cached version that has the most needed, most wanted, least unwanted files, highest quality and largest size
                        release.files.sort(key=lambda x: len(x.files), reverse=True)
                        release.files.sort(
                            key=lambda x: x.size, reverse=True
                        )  # Sort by size (larger is better)
                        release.files.sort(key=lambda x: x.wanted, reverse=True)
                        release.files.sort(key=lambda x: x.unwanted, reverse=False)
                        release.wanted = release.files[0].wanted
                        release.unwanted = release.files[0].unwanted
                        release.size = release.files[0].size
                        release.cached += ["RD"]
                        continue

        # Sort releases by quality and size to prioritize best quality
        ui_print(
            "[realdebrid] sorting releases by quality and size...", ui_settings.debug
        )
        element.Releases.sort(
            key=lambda x: getattr(x, "size", 0), reverse=True
        )  # Larger files first
        ui_print("done", ui_settings.debug)


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
