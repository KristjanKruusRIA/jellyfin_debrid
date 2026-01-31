# import modules
import releases
from base import SimpleNamespace, copy, custom_session, json, regex, time
from ui.ui_print import ui_print, ui_settings

name = "aiostreams"

# AIOStreams configuration - set by settings system from settings.json
base_url = "https://aiostreamsfortheweebs.midnightignite.me"
uuid = ""
b64config = ""

session = custom_session()
# Use a browser-like User-Agent
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
)


def get(url):
    try:
        response = session.get(url, timeout=60)
        response = json.loads(
            response.content, object_hook=lambda d: SimpleNamespace(**d)
        )
        return response
    except Exception:
        return None


def setup(cls, new=False):
    from scraper.services import active
    from settings import settings_list

    settings = []
    for category, allsettings in settings_list:
        for setting in allsettings:
            if setting.cls == cls:
                settings += [setting]
    if settings == []:
        if cls.name not in active:
            active += [cls.name]
    back = False
    if not new:
        while not back:
            print("0) Back")
            indices = []
            for index, setting in enumerate(settings):
                print(str(index + 1) + ") " + setting.name)
                indices += [str(index + 1)]
            print()
            if settings == []:
                print("Nothing to edit!")
                print()
                time.sleep(3)
                return
            choice = input("Choose an action: ")
            if choice in indices:
                settings[int(choice) - 1].input()
                if cls.name not in active:
                    active += [cls.name]
                back = True
            elif choice == "0":
                back = True
    else:
        if cls.name not in active:
            active += [cls.name]


def scrape(query, altquery):
    from scraper.services import active

    ui_print(
        '[aiostreams] debug: scrape called with query="' + str(query) + '"',
        ui_settings.debug,
    )

    if not uuid or not b64config:
        ui_print(
            "[aiostreams] error: AIOStreams UUID or B64Config not set in settings.json",
            ui_settings.debug,
        )
        return []

    ui_print(
        "[aiostreams] debug: UUID and B64Config loaded successfully", ui_settings.debug
    )

    scraped_releases = []
    if "aiostreams" not in active:
        ui_print(
            "[aiostreams] debug: aiostreams not in active scrapers", ui_settings.debug
        )
        return scraped_releases

    ui_print("[aiostreams] debug: aiostreams is active, proceeding", ui_settings.debug)
    if altquery == "(.*)":
        altquery = query
    type = (
        "show"
        if regex.search(r"(S[0-9]|complete|S\?[0-9])", altquery, regex.I)
        else "movie"
    )

    # Determine season and episode numbers if it's a show
    if type == "show":
        s = (
            regex.search(r"(?<=S)([0-9]+)", altquery, regex.I).group()
            if regex.search(r"(?<=S)([0-9]+)", altquery, regex.I)
            else None
        )
        e = (
            regex.search(r"(?<=E)([0-9]+)", altquery, regex.I).group()
            if regex.search(r"(?<=E)([0-9]+)", altquery, regex.I)
            else None
        )
        if s is None or int(s) == 0:
            s = 1
        # Keep e as None if not specified - will query for season pack

    # Get IMDB ID from query or resolve it
    plain_text = ""
    if regex.search(r"(tt[0-9]+)", altquery, regex.I):
        query = regex.search(r"(tt[0-9]+)", altquery, regex.I).group()
    else:
        plain_text = copy.deepcopy(query)
        try:
            if type == "show":
                url = (
                    "https://v3-cinemeta.strem.io/catalog/series/top/search="
                    + query
                    + ".json"
                )
                meta = get(url)
            else:
                url = (
                    "https://v3-cinemeta.strem.io/catalog/movie/top/search="
                    + query
                    + ".json"
                )
                meta = get(url)
            query = meta.metas[0].imdb_id
        except Exception:
            try:
                if type == "movie":
                    type = "show"
                    s = 1
                    e = 1
                    url = (
                        "https://v3-cinemeta.strem.io/catalog/series/top/search="
                        + query
                        + ".json"
                    )
                    meta = get(url)
                else:
                    type = "movie"
                    url = (
                        "https://v3-cinemeta.strem.io/catalog/movie/top/search="
                        + query
                        + ".json"
                    )
                    meta = get(url)
                query = meta.metas[0].imdb_id
            except Exception:
                ui_print("[aiostreams] error: could not find IMDB ID")
                return scraped_releases

    # Query the AIOStreams service
    if type == "movie":
        url = (
            base_url
            + "/stremio/"
            + uuid
            + "/"
            + b64config
            + "/stream/movie/"
            + query
            + ".json"
        )
        ui_print("[aiostreams] debug: querying movie API: " + url, ui_settings.debug)
        response = get(url)
        ui_print(
            "[aiostreams] debug: movie response: " + str(response), ui_settings.debug
        )
        if (
            not response
            or not hasattr(response, "streams")
            or len(response.streams) == 0
        ):
            ui_print(
                "[aiostreams] debug: no movie results, trying as show",
                ui_settings.debug,
            )
            type = "show"
            s = 1
            e = 1
            if plain_text != "":
                try:
                    url = (
                        "https://v3-cinemeta.strem.io/catalog/series/top/search="
                        + plain_text
                        + ".json"
                    )
                    meta = get(url)
                    query = meta.metas[0].imdb_id
                except Exception as e:
                    ui_print("[aiostreams] error: could not find IMDB ID: " + str(e))
                    return scraped_releases

    if type == "show":
        # If episode number specified, query specific episode
        if e is not None and int(e) > 0:
            url = (
                base_url
                + "/stremio/"
                + uuid
                + "/"
                + b64config
                + "/stream/series/"
                + query
                + ":"
                + str(int(s))
                + ":"
                + str(int(e))
                + ".json"
            )
            ui_print(
                "[aiostreams] debug: querying show API (specific episode): " + url,
                ui_settings.debug,
            )
        else:
            # No episode specified - query for season pack
            url = (
                base_url
                + "/stremio/"
                + uuid
                + "/"
                + b64config
                + "/stream/series/"
                + query
                + ".json"
            )
            ui_print(
                "[aiostreams] debug: querying show API (season pack): " + url,
                ui_settings.debug,
            )
        response = get(url)
        ui_print(
            "[aiostreams] debug: show response: " + str(response), ui_settings.debug
        )

    if not response or not hasattr(response, "streams"):
        try:
            if response is not None:
                ui_print("[aiostreams] error: " + str(response))
        except Exception:
            ui_print("[aiostreams] error: unknown error")
        return scraped_releases
    elif len(response.streams) == 1 and not hasattr(response.streams[0], "title"):
        ui_print("[aiostreams] error: no streams found or API error")
        return scraped_releases

    # Parse the stream results - AIOStreams returns direct download URLs
    # Streams are ordered by quality/size (best first), so prioritize stream 0
    ui_print(
        "[aiostreams] debug: found " + str(len(response.streams)) + " streams",
        ui_settings.debug,
    )
    for idx, result in enumerate(response.streams):
        try:
            # Extract URL first
            stream_url = None
            if hasattr(result, "url") and result.url:
                stream_url = result.url
            else:
                continue

            # Extract filename - Sootio/AIOStreams provides filename in behaviorHints
            filename = None
            filename_from_url = None

            # Always extract filename from URL as a fallback (this includes the extension)
            try:
                from urllib.parse import unquote

                decoded_url = unquote(stream_url)
                filename_from_url = (
                    decoded_url.split("/")[-1].split("?")[0]
                    if "/" in decoded_url
                    else None
                )
            except Exception:
                filename_from_url = (
                    stream_url.split("/")[-1].split("?")[0]
                    if "/" in stream_url
                    else None
                )

            # Method 1: Check behaviorHints.filename (most reliable for Sootio/AIOStreams)
            if (
                hasattr(result, "behaviorHints")
                and hasattr(result.behaviorHints, "filename")
                and result.behaviorHints.filename
            ):
                raw_filename = str(result.behaviorHints.filename)
                # Remove [Cloud] prefix and leading slashes
                filename = (
                    raw_filename.replace("[Cloud] ", "")
                    .replace("[Cloud]", "")
                    .lstrip("/")
                )

            # Method 2: Check name field (Sootio streams may have filename here)
            if not filename and hasattr(result, "name") and result.name:
                # Sootio format: "filename\n🔗 provider | source" or direct URLs
                name_lines = str(result.name).split("\n")
                if name_lines and name_lines[0].strip():
                    potential_filename = name_lines[0].strip()

                    # If it's a full URL, extract just the filename
                    if potential_filename.startswith(
                        "http://"
                    ) or potential_filename.startswith("https://"):
                        filename = potential_filename.split("/")[-1].split("?")[0]
                    # If it's a real filename (has extension and not a Sootio ID)
                    elif (
                        "." in potential_filename
                        and not potential_filename.startswith("realdebrid:")
                    ):
                        filename = potential_filename

            # Method 3: Check description field (Sootio alternate format)
            if not filename and hasattr(result, "description") and result.description:
                desc_lines = str(result.description).split("\n")
                if desc_lines and desc_lines[0].strip():
                    potential_filename = desc_lines[0].strip()

                    # If it's a URL, extract the filename
                    if potential_filename.startswith(
                        "http://"
                    ) or potential_filename.startswith("https://"):
                        filename = potential_filename.split("/")[-1].split("?")[0]
                    # If it's a real filename
                    elif (
                        "." in potential_filename
                        and not potential_filename.startswith("realdebrid:")
                    ):
                        filename = potential_filename

            # Method 4: Fallback to URL-extracted filename
            if not filename and filename_from_url:
                filename = filename_from_url
            elif not filename:
                filename = "Unknown"

            # URL decode the filename if needed (in case it wasn't from URL extraction)
            try:
                from urllib.parse import unquote

                filename = unquote(filename)
            except Exception:
                pass

            # If filename doesn't have an extension but URL filename does, use the URL extension
            import os

            filename_ext = os.path.splitext(filename)[1].lower()
            if not filename_ext and filename_from_url:
                url_ext = os.path.splitext(filename_from_url)[1].lower()
                if url_ext in [
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
                    ".ts",
                    ".m2ts",
                ]:
                    filename = filename + url_ext

            ui_print(
                "[aiostreams] debug: stream "
                + str(idx)
                + " filename: "
                + str(filename),
                ui_settings.debug,
            )

            # Clean up title for display - remove query string parameters and file extensions
            title = filename.split("?")[0]  # Remove query string (?name=..., etc)
            title = (
                title.replace(".mkv", "")
                .replace(".mp4", "")
                .replace(".avi", "")
                .replace(" ", ".")
            )

            # Extract size from the 'size' field (in bytes) and convert to GB
            size = 0
            if hasattr(result, "size") and result.size:
                try:
                    size_bytes = float(result.size)
                    size = size_bytes / (1024 * 1024 * 1024)  # Convert bytes to GB
                    ui_print(
                        "[aiostreams] debug: stream "
                        + str(idx)
                        + " size from API: "
                        + str(size)
                        + "GB",
                        ui_settings.debug,
                    )
                except Exception:
                    size = 0

            # Fallback: try to extract from description if size field not available
            if size == 0 and hasattr(result, "description") and result.description:
                try:
                    size_match = regex.search(
                        r"([0-9]+\.?[0-9]*)\s*(GB|MB|TB)",
                        str(result.description),
                        regex.I,
                    )
                    if size_match:
                        size_val = float(size_match.group(1))
                        unit = size_match.group(2).upper()
                        if unit == "GB":
                            size = size_val
                        elif unit == "MB":
                            size = size_val / 1024
                        elif unit == "TB":
                            size = size_val * 1024
                except Exception:
                    size = 0

            # AIOStreams provides direct HTTP links (cached/debrid)
            release_type = "http"

            # Extract seeders if present
            seeds = 0
            if hasattr(result, "torrent") and result.torrent:
                try:
                    if hasattr(result.torrent, "seeders"):
                        seeds = int(result.torrent.seeders)
                except Exception:
                    seeds = 0

            # Extract source provider from service info
            plugin_name = None
            service_name = None

            # Extract plugin name from the name field (e.g., "[RD☁️⚡] Sootio 1080p" -> "Sootio")
            if hasattr(result, "name") and result.name:
                try:
                    # Pattern: "[prefix] PluginName quality" - extract text between ] and quality marker
                    name_match = regex.search(r"\]\s+([A-Za-z0-9]+)", str(result.name))
                    if name_match:
                        plugin_name = name_match.group(1).strip()
                except Exception:
                    pass

            # Extract service from behaviorHints.bingeGroup (pipe-separated format)
            # Format: "domain|service|cached|quality|..." where service is what we want
            if hasattr(result, "behaviorHints") and hasattr(
                result.behaviorHints, "bingeGroup"
            ):
                try:
                    binge_parts = str(result.behaviorHints.bingeGroup).split("|")
                    if len(binge_parts) >= 2:
                        service_name = binge_parts[1].strip()
                except Exception:
                    pass

            # Build source string: aiostreams:plugin:service or fallback variations
            if plugin_name and service_name:
                source = f"{plugin_name.lower()}:{service_name}"
            elif plugin_name:
                source = plugin_name.lower()
            elif service_name:
                source = service_name
            else:
                source = "aiostreams"

            # Fallback: Try result.service.id (older format)
            if source == "aiostreams" and hasattr(result, "service") and result.service:
                try:
                    if hasattr(result.service, "id"):
                        source = str(result.service.id)
                except Exception:
                    pass

            # Create release object with the direct HTTP link
            links = [stream_url]
            release = releases.release(
                "[aiostreams: " + source + "]",
                release_type,
                title,
                [],
                size,
                links,
                seeds,
            )

            # Ensure type attribute is set for HTTP releases
            release.type = "http"
            # Store actual filename (including extension) for downloader fallback
            real_filename = filename.split("?")[0]
            release.filenames = [real_filename]

            ui_print(
                "[aiostreams] debug: added release: "
                + title
                + " | size: "
                + str(size)
                + "GB | seeders: "
                + str(seeds)
                + " | type: "
                + str(release.type)
                + " | download[0]: "
                + str(stream_url[:80])
                + "...",
                ui_settings.debug,
            )
            scraped_releases += [release]

        except Exception as e:
            ui_print("[aiostreams] error parsing stream: " + str(e), ui_settings.debug)
            import traceback

            ui_print(
                "[aiostreams] traceback: " + traceback.format_exc(), ui_settings.debug
            )
            continue

    ui_print(
        "[aiostreams] debug: returning " + str(len(scraped_releases)) + " releases",
        ui_settings.debug,
    )
    return scraped_releases
