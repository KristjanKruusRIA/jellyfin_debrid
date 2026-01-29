# import modules
import releases
from base import SimpleNamespace, copy, custom_session, json, regex, time
from ui.ui_print import ui_print, ui_settings

name = "torrentio"

# Default options — includes quality filters and client-side limit
default_opts = "https://torrentio.strem.fun/qualityfilter=threed,720p,480p,scr,cam|limit=5|debridoptions=nodownloadlinks/manifest.json"

session = custom_session()
# Use a browser-like User-Agent and accept JSON to avoid remote server blocking Python requests
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

    scraped_releases = []
    if "torrentio" not in active:
        return scraped_releases
    if altquery == "(.*)":
        altquery = query
    type = (
        "show"
        if regex.search(r"(S[0-9]|complete|S\?[0-9])", altquery, regex.I)
        else "movie"
    )
    opts = default_opts.split("/")[-2] if default_opts.endswith("manifest.json") else ""
    # Parse optional limit from opts (e.g., '...|limit=5') and enforce client-side
    limit = None
    try:
        m = regex.search(r"limit=([0-9]+)", opts)
        if m:
            limit = int(m.group(1))
    except Exception:
        limit = None
    # Parse debrid options (e.g., 'debridoptions=nodownloadlinks')
    nodownloadlinks = False
    try:
        m = regex.search(r"debridoptions=([^|]+)", opts)
        if m and "nodownloadlinks" in m.group(1).split(","):
            nodownloadlinks = True
            ui_print(
                "[torrentio] using debridoptions=nodownloadlinks", ui_settings.debug
            )
    except Exception:
        nodownloadlinks = False
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
        if e is None or int(e) == 0:
            e = 1
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
                ui_print("[torrentio] error: could not find IMDB ID")
                return scraped_releases
    if type == "movie":
        url = (
            "https://torrentio.strem.fun/"
            + opts
            + ("/" if len(opts) > 0 else "")
            + "stream/movie/"
            + query
            + ".json"
        )
        response = get(url)
        if not hasattr(response, "streams") or len(response.streams) == 0:
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
                    ui_print("[torrentio] error: could not find IMDB ID: " + str(e))
                    return scraped_releases
    if type == "show":
        url = (
            "https://torrentio.strem.fun/"
            + opts
            + ("/" if len(opts) > 0 else "")
            + "stream/series/"
            + query
            + ":"
            + str(int(s))
            + ":"
            + str(int(e))
            + ".json"
        )
        response = get(url)
    if not hasattr(response, "streams"):
        try:
            if response is not None:
                ui_print("[torrentio] error: " + str(response))
        except Exception:
            ui_print("[torrentio] error: unknown error")
        return scraped_releases
    elif len(response.streams) == 1 and not hasattr(response.streams[0], "infoHash"):
        ui_print(
            '[torrentio] error: "'
            + response.streams[0].name.replace("\n", " ")
            + '" - '
            + response.streams[0].title.replace("\n", " ")
        )
        return scraped_releases
    count = 0
    for result in response.streams:
        if limit and count >= limit:
            break
        try:
            title = result.title.split("\n")[0].replace(" ", ".")
            size = (
                float(
                    regex.search(
                        r"(?<=💾 )([0-9]+.?[0-9]+)(?= GB)", result.title
                    ).group()
                )
                if regex.search(r"(?<=💾 )([0-9]+.?[0-9]+)(?= GB)", result.title)
                else (
                    float(
                        regex.search(
                            r"(?<=💾 )([0-9]+.?[0-9]+)(?= MB)", result.title
                        ).group()
                    )
                    / 1000
                    if regex.search(r"(?<=💾 )([0-9]+.?[0-9]+)(?= MB)", result.title)
                    else 0
                )
            )
            links = ["magnet:?xt=urn:btih:" + result.infoHash + "&dn=&tr="]
            seeds = (
                int(regex.search(r"(?<=👤 )([0-9]+)", result.title).group())
                if regex.search(r"(?<=👤 )([1-9]+)", result.title)
                else 0
            )
            source = (
                (regex.search(r"(?<=⚙️ )(.*)(?=\n|$)", result.title).group())
                if regex.search(r"(?<=⚙️ )(.*)(?=\n|$)", result.title)
                else "unknown"
            )
            release = releases.release(
                "[torrentio: " + source + "]", "torrent", title, [], size, links, seeds
            )
            # If nodownloadlinks is enabled, Torrentio only returns cached results
            # Mark them as cached for RealDebrid to skip the cache check
            if nodownloadlinks:
                release.cached = [
                    "RD"
                ]  # Assume RealDebrid since that's the primary service
                ui_print(
                    "[torrentio] marking release as cached (nodownloadlinks enabled): "
                    + title,
                    ui_settings.debug,
                )
            scraped_releases += [release]
            count += 1
        except Exception:
            continue
    return scraped_releases
