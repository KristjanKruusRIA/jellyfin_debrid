# import modules
import releases
from base import SimpleNamespace, copy, custom_session, json, regex, time
from ui.ui_print import ui_print, ui_settings

name = "comet"

# Comet configuration - set by settings system from settings.json
base_url = ""
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
        '[comet] debug: scrape called with query="' + str(query) + '"',
        ui_settings.debug,
    )

    if not b64config:
        ui_print(
            "[comet] error: Comet B64Config not set in settings.json",
            ui_settings.debug,
        )
        return []

    ui_print("[comet] debug: B64Config loaded successfully", ui_settings.debug)

    scraped_releases = []
    if "comet" not in active:
        ui_print("[comet] debug: comet not in active scrapers", ui_settings.debug)
        return scraped_releases

    ui_print("[comet] debug: comet is active, proceeding", ui_settings.debug)
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
                ui_print("[comet] error: could not find IMDB ID")
                return scraped_releases

    # Query the Comet service
    if type == "movie":
        url = base_url + "/" + b64config + "/stream/movie/" + query + ".json"
        ui_print("[comet] debug: querying movie API: " + url, ui_settings.debug)
        response = get(url)
        ui_print("[comet] debug: movie response: " + str(response), ui_settings.debug)
        if (
            not response
            or not hasattr(response, "streams")
            or len(response.streams) == 0
        ):
            ui_print(
                "[comet] debug: no movie results, trying as show",
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
                    ui_print("[comet] error: could not find IMDB ID: " + str(e))
                    return scraped_releases

    if type == "show":
        # Check if this is a season pack request (e is None or 0) or specific episode
        if e is None or int(e) == 0:
            # Season pack query - use plain IMDB ID without episode suffix
            url = base_url + "/" + b64config + "/stream/series/" + query + ".json"
            ui_print(
                "[comet] debug: querying show API (season pack S"
                + str(s).zfill(2)
                + "): "
                + url,
                ui_settings.debug,
            )
        else:
            # Specific episode query - include season and episode numbers
            url = (
                base_url
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
                "[comet] debug: querying show API (S"
                + str(s).zfill(2)
                + "E"
                + str(e).zfill(2)
                + "): "
                + url,
                ui_settings.debug,
            )

        response = get(url)
        ui_print("[comet] debug: show response: " + str(response), ui_settings.debug)

    if not response or not hasattr(response, "streams"):
        try:
            if response is not None:
                ui_print("[comet] error: " + str(response))
        except Exception:
            ui_print("[comet] error: unknown error")
        return scraped_releases
    elif len(response.streams) == 1 and not hasattr(response.streams[0], "title"):
        ui_print("[comet] error: no streams found or API error")
        return scraped_releases

    # Parse the stream results - Comet returns torrent info hashes
    # Streams are ordered by quality/size (best first), so prioritize stream 0
    ui_print(
        "[comet] debug: found " + str(len(response.streams)) + " streams",
        ui_settings.debug,
    )
    for idx, result in enumerate(response.streams):
        try:
            # Check if this is an error stream from Comet
            if hasattr(result, "name") and (
                "[⛔️]" in str(result.name)
                or "Non-debrid searches disabled"
                in str(result.description if hasattr(result, "description") else "")
            ):
                ui_print(
                    "[comet] warning: "
                    + str(result.name)
                    + " - "
                    + str(result.description if hasattr(result, "description") else ""),
                    ui_settings.debug,
                )
                continue

            # Extract info hash from the result
            info_hash = None
            if hasattr(result, "infoHash") and result.infoHash:
                info_hash = result.infoHash
            elif hasattr(result, "url") and result.url:
                # Try to extract info hash from URL
                hash_match = regex.search(r"([a-fA-F0-9]{40})", result.url, regex.I)
                if hash_match:
                    info_hash = hash_match.group(1)

            if not info_hash:
                ui_print(
                    "[comet] debug: stream " + str(idx) + " has no info hash, skipping",
                    ui_settings.debug,
                )
                continue

            # Extract title from the result
            title = None
            if hasattr(result, "title") and result.title:
                title = str(result.title).strip()
            elif hasattr(result, "name") and result.name:
                title = str(result.name).strip()
            else:
                title = "Unknown"

            ui_print(
                "[comet] debug: stream " + str(idx) + " title: " + str(title),
                ui_settings.debug,
            )

            # Extract size from the result (Comet typically provides this in description or size field)
            size = 0
            if hasattr(result, "size") and result.size:
                try:
                    size_bytes = float(result.size)
                    size = size_bytes / (1024 * 1024 * 1024)  # Convert bytes to GB
                    ui_print(
                        "[comet] debug: stream "
                        + str(idx)
                        + " size from API: "
                        + str(size)
                        + "GB",
                        ui_settings.debug,
                    )
                except Exception:
                    size = 0

            # Fallback: try to extract from description or name if size field not available
            if size == 0:
                search_text = ""
                if hasattr(result, "description") and result.description:
                    search_text = str(result.description)
                elif hasattr(result, "name") and result.name:
                    search_text = str(result.name)

                if search_text:
                    try:
                        size_match = regex.search(
                            r"([0-9]+\.?[0-9]*)\s*(GB|MB|TB)",
                            search_text,
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

            # Comet provides torrent info hashes
            release_type = "torrent"

            # Extract seeders if present
            seeds = 0
            if hasattr(result, "seeders") and result.seeders:
                try:
                    seeds = int(result.seeders)
                except Exception:
                    seeds = 0
            elif hasattr(result, "torrent") and result.torrent:
                try:
                    if hasattr(result.torrent, "seeders"):
                        seeds = int(result.torrent.seeders)
                except Exception:
                    seeds = 0

            # Build magnet link from info hash with display name parameter
            # The &dn= parameter is required for the release class regex to extract the hash
            from urllib.parse import quote

            magnet_link = "magnet:?xt=urn:btih:" + info_hash + "&dn=" + quote(title)

            # Create release object with the magnet link
            links = [magnet_link]
            release = releases.release(
                "[comet]",
                release_type,
                title,
                [info_hash],
                size,
                links,
                seeds,
            )

            ui_print(
                "[comet] debug: added release: "
                + title
                + " | size: "
                + str(size)
                + "GB | seeders: "
                + str(seeds)
                + " | hash: "
                + info_hash,
                ui_settings.debug,
            )
            scraped_releases += [release]

        except Exception as e:
            ui_print("[comet] error parsing stream: " + str(e), ui_settings.debug)
            import traceback

            ui_print("[comet] traceback: " + traceback.format_exc(), ui_settings.debug)
            continue

    ui_print(
        "[comet] debug: returning " + str(len(scraped_releases)) + " releases",
        ui_settings.debug,
    )
    return scraped_releases
