from types import SimpleNamespace

import regex
import requests

import downloader
from ui.ui_print import ui_print, ui_settings

name = "TorBox"
short = "TB"
api_key = ""

session = requests.Session()
BASE_URL = "https://api.torbox.app"
_VIDEO_EXTENSIONS = (
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
)


def setup(cls, new=False):
    from debrid.services import setup as debrid_setup

    debrid_setup(cls, new)


def _headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "authorization": "Bearer " + api_key,
    }


def _to_namespace(value):
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_to_namespace(v) for v in value]
    return value


def _to_plain(value):
    if isinstance(value, SimpleNamespace):
        return {k: _to_plain(v) for k, v in vars(value).items()}
    if isinstance(value, list):
        return [_to_plain(v) for v in value]
    return value


def _logerror(response, context=None):
    if response.status_code in [200, 201, 204]:
        return
    detail = ""
    try:
        parsed = response.json()
        detail = str(parsed.get("detail") or parsed.get("error") or "")
    except Exception:
        detail = str(response.content)
    extra = (" Context: " + str(context)) if context else ""
    ui_print(
        "[torbox] error: (" + str(response.status_code) + ") " + detail + extra,
        debug=ui_settings.debug,
    )


def _request(method, path, *, params=None, data=None, files=None, context=None):
    response = None
    try:
        response = session.request(
            method=method,
            url=BASE_URL + path,
            headers=_headers(),
            params=params,
            data=data,
            files=files,
            timeout=30,
        )
        _logerror(response, context=context)
        if not response.content:
            return None
        payload = response.json()
        return _to_namespace(payload)
    except Exception as exc:
        ui_print(
            "[torbox] error: (request/json exception): "
            + str(exc)
            + ((" Context: " + str(context)) if context else ""),
            debug=ui_settings.debug,
        )
        return None


def get(path, params=None, context=None):
    return _request("GET", path, params=params, context=context)


def post(path, data=None, files=None, context=None):
    return _request("POST", path, data=data, files=files, context=context)


def _is_success(payload):
    return bool(payload and getattr(payload, "success", False))


def _extract_cached_hashes(data):
    plain = _to_plain(data)
    cached_hashes = set()

    if isinstance(plain, dict):
        for key, value in plain.items():
            if isinstance(key, str) and len(key) == 40:
                if isinstance(value, bool):
                    if value:
                        cached_hashes.add(key.lower())
                    continue
                if isinstance(value, list) and len(value) > 0:
                    cached_hashes.add(key.lower())
                    continue
                if isinstance(value, dict):
                    if value.get("cached") is True:
                        cached_hashes.add(key.lower())
                        continue
                    if len(value) > 0:
                        cached_hashes.add(key.lower())

    if isinstance(plain, list):
        for item in plain:
            if not isinstance(item, dict):
                continue
            hash_value = str(item.get("hash", "")).lower()
            if len(hash_value) != 40:
                continue
            if item.get("cached") is True:
                cached_hashes.add(hash_value)
                continue
            if isinstance(item.get("files"), list) and len(item.get("files")) > 0:
                cached_hashes.add(hash_value)

    return cached_hashes


def _extract_torrent_id(payload):
    if not payload:
        return None

    data = _to_plain(getattr(payload, "data", None))

    possible = []
    if isinstance(data, dict):
        possible += [
            data.get("id"),
            data.get("torrent_id"),
            data.get("torrentId"),
            data.get("download_id"),
        ]
    possible += [getattr(payload, "id", None), getattr(payload, "torrent_id", None)]

    for value in possible:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _extract_download_url(payload):
    if not payload:
        return None
    data = _to_plain(getattr(payload, "data", None))
    if isinstance(data, str) and data:
        return data
    if isinstance(data, dict):
        for key in ["url", "download", "link", "download_url", "cdn_link"]:
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
    for key in ["url", "download", "link"]:
        value = getattr(payload, key, None)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_torrent_info(payload, torrent_id):
    if not payload:
        return None

    data = _to_plain(getattr(payload, "data", None))
    if isinstance(data, dict):
        if isinstance(data.get("id"), int) and data["id"] == torrent_id:
            return data
        if isinstance(data.get("torrent_id"), int) and data["torrent_id"] == torrent_id:
            return data
        for key in ["torrents", "items", "results"]:
            listing = data.get(key)
            if isinstance(listing, list):
                for item in listing:
                    if not isinstance(item, dict):
                        continue
                    item_id = item.get("id", item.get("torrent_id"))
                    if item_id == torrent_id:
                        return item

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id", item.get("torrent_id"))
            if item_id == torrent_id:
                return item

    return None


def _post_download_cleanup(element):
    import debrid as db

    download_id = element.query()
    if hasattr(element, "version"):
        download_id += " [" + element.version.name + "]"
    if download_id in db.downloading:
        db.downloading.remove(download_id)

    try:
        from content.services import jellyfin

        jellyfin.library.refresh(element)
    except Exception as exc:
        ui_print(
            "[torbox] could not refresh jellyfin libraries: " + str(exc),
            debug=ui_settings.debug,
        )

    try:
        from content.services import seerr

        seerr.library.refresh(element)
    except Exception as exc:
        ui_print(
            "[torbox] could not mark seerr request as available: " + str(exc),
            debug=ui_settings.debug,
        )


def _fetch_release_links(release, torrent_id, context=None):
    list_payload = get(
        "/v1/api/torrents/mylist",
        params={"id": torrent_id, "bypass_cache": "true"},
        context=context,
    )
    if not _is_success(list_payload):
        return False

    torrent_info = _extract_torrent_info(list_payload, torrent_id)
    files = []
    if isinstance(torrent_info, dict):
        maybe_files = torrent_info.get("files")
        if isinstance(maybe_files, list):
            files = maybe_files

    selected_files = []
    for file_info in files:
        if not isinstance(file_info, dict):
            continue
        file_id = file_info.get("id", file_info.get("file_id"))
        if not isinstance(file_id, int):
            continue
        filename = str(
            file_info.get("name")
            or file_info.get("path")
            or file_info.get("filename")
            or ("file_" + str(file_id))
        )
        if "/" in filename:
            filename = filename.split("/")[-1]
        if filename.lower().endswith(_VIDEO_EXTENSIONS):
            selected_files.append({"id": file_id, "name": filename})

    if len(selected_files) == 0:
        for file_info in files:
            if not isinstance(file_info, dict):
                continue
            file_id = file_info.get("id", file_info.get("file_id"))
            if not isinstance(file_id, int):
                continue
            filename = str(
                file_info.get("name")
                or file_info.get("path")
                or file_info.get("filename")
                or ("file_" + str(file_id))
            )
            if "/" in filename:
                filename = filename.split("/")[-1]
            selected_files.append({"id": file_id, "name": filename})

    links = []
    filenames = []
    for file_entry in selected_files:
        dl_payload = get(
            "/v1/api/torrents/requestdl",
            params={
                "token": api_key,
                "torrent_id": torrent_id,
                "file_id": file_entry["id"],
                "redirect": "false",
            },
            context=context,
        )
        if not _is_success(dl_payload):
            continue
        download_url = _extract_download_url(dl_payload)
        if isinstance(download_url, str) and download_url:
            links.append(download_url)
            filenames.append(file_entry["name"])

    if len(links) == 0:
        dl_payload = get(
            "/v1/api/torrents/requestdl",
            params={
                "token": api_key,
                "torrent_id": torrent_id,
                "redirect": "false",
            },
            context=context,
        )
        if _is_success(dl_payload):
            download_url = _extract_download_url(dl_payload)
            if isinstance(download_url, str) and download_url:
                links.append(download_url)
                filenames.append(str(release.title))

    if len(links) == 0:
        return False

    release.download = links
    release.filenames = filenames
    return True


def download(element, query="", force=False):
    cached = element.Releases
    if query == "":
        query = element.deviation()

    alternative_query = None
    if hasattr(element, "type") and element.type == "episode":
        parent_index = getattr(element, "parentIndex", None)
        if parent_index is not None:
            alternative_query = f"S{parent_index:02d}"

    for release in cached[:]:
        is_http_release = hasattr(release, "type") and release.type == "http"
        matches_primary = regex.match(query, release.title, regex.I)
        if is_http_release:
            matches_alternative = False
        else:
            matches_alternative = (
                alternative_query and alternative_query.lower() in release.title.lower()
            )
        is_cached = hasattr(release, "cached") and short in release.cached

        if not (matches_primary or matches_alternative or force or is_cached):
            ui_print(
                '[torbox] error: rejecting release: "'
                + release.title
                + '" because it does not match the allowed deviation',
                ui_settings.debug,
            )
            continue

        if is_http_release:
            if hasattr(release, "download") and len(release.download) > 0:
                ok = downloader.download_from_realdebrid(release, element)
                if ok:
                    ui_print("[torbox] download complete (http)")
                    _post_download_cleanup(element)
                    return True
            continue

        context = (
            "release: '"
            + str(release.title)
            + "' | item: '"
            + str(element.query())
            + "'"
        )
        magnet = ""
        if (
            hasattr(release, "download")
            and release.download
            and len(release.download) > 0
        ):
            magnet = str(release.download[0])

        if not magnet.startswith("magnet:"):
            ui_print(
                "[torbox] error: invalid download link (not magnet): " + str(magnet),
                debug=ui_settings.debug,
            )
            continue

        create_payload = post(
            "/v1/api/torrents/createtorrent",
            data={
                "magnet": magnet,
                "add_only_if_cached": "true",
                "as_queued": "false",
            },
            context=context,
        )
        if not _is_success(create_payload):
            ui_print(
                "[torbox] failed to create torrent for release: " + str(release.title),
                debug=ui_settings.debug,
            )
            continue

        torrent_id = _extract_torrent_id(create_payload)
        if torrent_id is None:
            ui_print(
                "[torbox] failed to determine torrent_id for release: "
                + str(release.title),
                debug=ui_settings.debug,
            )
            continue

        if not _fetch_release_links(release, torrent_id, context=context):
            ui_print(
                "[torbox] no downloadable links available for release: "
                + str(release.title),
                debug=ui_settings.debug,
            )
            continue

        release.size = 0
        ok = downloader.download_from_realdebrid(release, element)
        if ok:
            ui_print("[torbox] download complete (torrent)")
            _post_download_cleanup(element)
            return True

    return False


def check(element, force=False):
    http_count = 0
    ignored_count = 0
    uncached_count = 0

    hash_to_release = {}
    hashes = []
    for release in element.Releases[:]:
        if hasattr(release, "type") and release.type == "http":
            release.cached += [short]
            http_count += 1
            continue

        release_hash = str(getattr(release, "hash", "")).lower()
        if len(release_hash) == 40:
            hashes.append(release_hash)
            hash_to_release[release_hash] = release
        else:
            ui_print(
                "[torbox] error (missing torrent hash): ignoring release '"
                + release.title
                + "' ",
                ui_settings.debug,
            )
            element.Releases.remove(release)
            ignored_count += 1

    cached_hashes = set()
    if len(hashes) > 0:
        payload = get(
            "/v1/api/torrents/checkcached",
            params={"hash": hashes, "format": "object", "list_files": "false"},
            context="hash_count=" + str(len(hashes)),
        )
        if _is_success(payload):
            cached_hashes = _extract_cached_hashes(getattr(payload, "data", None))

    for release_hash, release in list(hash_to_release.items()):
        if release_hash in cached_hashes:
            release.cached += [short]
            release.files = []
        else:
            element.Releases.remove(release)
            uncached_count += 1

    element.Releases.sort(key=lambda x: getattr(x, "size", 0), reverse=True)
    ui_print(
        "[torbox] marked "
        + str(len(element.Releases))
        + " releases as cached"
        + (
            " ["
            + str(http_count)
            + " http, "
            + str(len(element.Releases) - http_count)
            + " torrent]"
            if http_count
            else ""
        )
        + (" [" + str(ignored_count) + " invalid hash]" if ignored_count else "")
        + (" [" + str(uncached_count) + " uncached]" if uncached_count else ""),
        ui_settings.debug,
    )
