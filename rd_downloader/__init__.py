# Real-Debrid Existing Torrents Downloader
# Downloads files from torrents already in your RD account

import regex

import debrid.services.realdebrid as rd
import downloader
from ui.ui_print import ui_print


def download_from_existing_torrents(query_title, is_show=False):
    """
    Check existing RD torrents and download matching files
    Returns True if a match was found and downloaded
    """
    try:
        ui_print(
            f"[rd_downloader] Checking existing RD torrents for: {query_title}",
            debug="true",
        )

        # Get list of torrents from RD account
        torrents = rd.torrents_list(limit=200)
        if not torrents:
            return False

        # Search for matching torrent
        query_clean = regex.sub(r"[^a-z0-9]+", ".", query_title.lower())

        for torrent in torrents:
            if not hasattr(torrent, "filename") or not hasattr(torrent, "status"):
                continue

            torrent_name = torrent.filename.lower()

            # Check if torrent name matches query
            if query_clean in torrent_name or regex.search(query_clean, torrent_name):
                ui_print(
                    f"[rd_downloader] Found matching torrent: {torrent.filename}",
                    debug="true",
                )

                # Check if torrent is ready (downloaded)
                if torrent.status in ["downloaded", "seeding", "uploading"]:
                    # Get torrent info with links
                    torrent_info = rd.get(
                        f"https://api.real-debrid.com/rest/1.0/torrents/info/{torrent.id}"
                    )

                    if not torrent_info or not hasattr(torrent_info, "links"):
                        continue

                    # Build file list from torrent
                    files_to_download = []
                    if hasattr(torrent_info, "files"):
                        for file in torrent_info.files:
                            if hasattr(file, "selected") and file.selected == 1:
                                files_to_download.append(
                                    {
                                        "name": file.path.split("/")[-1]
                                        if hasattr(file, "path")
                                        else torrent.filename,
                                        "size": file.bytes
                                        if hasattr(file, "bytes")
                                        else 0,
                                        "id": file.id,
                                        "url": None,
                                    }
                                )

                    if not files_to_download:
                        files_to_download.append(
                            {
                                "name": torrent.filename,
                                "size": torrent.bytes
                                if hasattr(torrent, "bytes")
                                else 0,
                                "id": 0,
                                "url": None,
                            }
                        )

                    # Select best file
                    best_file = downloader.select_best_file(files_to_download)

                    if not best_file:
                        ui_print(
                            "[rd_downloader] No suitable file found in torrent",
                            debug="true",
                        )
                        continue

                    # Get unrestricted download links
                    unrestricted_links = []
                    for link in torrent_info.links:
                        try:
                            response = rd.post(
                                "https://api.real-debrid.com/rest/1.0/unrestrict/link",
                                {"link": link},
                            )
                            if hasattr(response, "download"):
                                unrestricted_links.append(response.download)
                        except Exception:
                            continue

                    if not unrestricted_links:
                        ui_print(
                            "[rd_downloader] Could not get download links", debug="true"
                        )
                        continue

                    # Download the best file
                    download_url = (
                        unrestricted_links[0]
                        if len(unrestricted_links) == 1
                        else unrestricted_links[best_file.get("id", 0)]
                        if best_file.get("id", 0) < len(unrestricted_links)
                        else unrestricted_links[0]
                    )

                    result = downloader.download_file(
                        download_url, best_file["name"], is_show
                    )

                    if result:
                        ui_print(
                            "[rd_downloader] Successfully downloaded from existing RD torrent",
                            debug="true",
                        )
                        return True

                elif torrent.status in ["queued", "downloading", "magnet_conversion"]:
                    ui_print(
                        f"[rd_downloader] Torrent is still downloading on RD: {torrent.status}",
                        debug="true",
                    )
                    return False

        ui_print("[rd_downloader] No matching existing torrents found", debug="true")
        return False

    except Exception as e:
        ui_print(
            f"[rd_downloader] Error checking existing torrents: {str(e)}", debug="true"
        )
        return False
