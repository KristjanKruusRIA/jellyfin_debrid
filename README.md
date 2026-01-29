# jellyfin_debrid
Jellyfin torrent downloading through Debrid Services, using Jellyseerr requests and watchlists.

Using content services like Jellyseerr, your personal media server users can add movies/shows to their watchlist and they become available to stream in minutes.

## Quick Start (Windows)

**New Windows-native installation (no Docker required!):**

1. Install Python 3.10+ and create virtual environment:
   ```powershell
   .\setup_venv.ps1
   ```

2. Configure your settings in `config\settings.json`

3. Verify setup:
   ```powershell
   .\verify_setup.ps1
   ```

4. Install as Windows service:
   - Right-click `install_autostart.bat` and run as administrator
   - Or manually start: `.\start_service.bat`

**For detailed Windows setup instructions, see [WINDOWS_SETUP.md](WINDOWS_SETUP.md)**

---
 
### In Action:

![ezgif com-gif-maker](https://user-images.githubusercontent.com/71379623/185643627-45217303-75d8-4c9d-8c8b-41bb2e27fd87.gif)
 
### Description:

A jellyfin_debrid setup consists of three parts.
- The first part is Jellyseerr which allows you to request media
- The second part is a personal media server (e.g., Jellyfin), which allows you to watch these files from anywhere on any device.
- The third part is the jellyfin_debrid script, which ties both things together and provides an easy way to download media content from your debrid service.

The jellyfin_debrid script monitors Jellyseerr requests (and optionally Overseerr) of specified users for newly added movies/shows and newly released episodes of watchlisted shows.

How it works:
- Monitor requests/watchlists from Jellyseerr (default) and Overseerr (optional).
- Scrape torrent indexers and streaming providers for candidate releases using configurable scrapers and version rules.
- Prefer cached releases on supported debrid services; if needed, add torrents to a debrid service and/or download directly.
- Validate downloads (size checks, ranged retries, progress reporting), sanitize and preserve filenames, then move files into organized Movies/Shows folders.
- Trigger a Jellyfin library refresh (full or partial) so new content becomes available for playback.

This workflow enables near-instant availability for cached content and robust, configurable automation for uncached downloads. 
 
### Features:
- Cross-platform: works on Windows, macOS, Linux and other Unix-like systems.
- Fast, configurable scanning: default polling interval is every 5 seconds (configurable) to pick up new Jellyseerr requests quickly.
- Sources:
  - Primary: Jellyseerr (requests/watchlists). Overseerr is supported as well.
  - Scrapers: Torrentio and AIOStreams (AIOStreams used for Easynews / direct HTTP sources).
- Debrid integration: supports RealDebrid.
- Download robustness: supports direct HTTP downloads and debrid APIs, temp-file downloads with progress reporting, ranged retries for partial responses, and size validation against expected size.
- Filenames and organization: sanitizes filenames for Windows, preserves extensions (including fixes for certain Easynews URL cases), and organizes files into:
  - Movies/Movie Name (Year)/filename
  - Shows/Show Name/Season XX/filename
- Quality selection: selects best candidate release,
- Integrations: triggers Jellyfin library refreshes after downloads and monitors Jellyseerr for requests.
- Configuration & logging: primary settings in `config/settings.json` (template at `settings.json.template`), AIOStreams requires env vars `AIOSTREAMS_UUID` and `AIOSTREAMS_B64CONFIG`, and detailed logs are written to `config/jellyfin_debrid.log`.

### Example minimal `settings.json` ✅

Below is a minimal example to get you started with Jellyfin + Jellyseerr + RealDebrid. Replace the placeholder values with your actual API keys and URLs.

```json
{
  "Content Services": ["jellyseerr"],
  "jellyseerr API Key": "YOUR_JELLYSEERR_API_KEY",
  "jellyseerr Base URL": "http://jellyseerr.local:5055",
  "Library collection service": "jellyseerr Library",
  "Library update services": ["Jellyseerr Requests"],
  "Debrid Services": ["Real Debrid"],
  "Real Debrid API Key": "YOUR_REALDEBRID_API_KEY",
  "Jellyfin server address": "http://jellyfin.local:8096",
  "Jellyfin API Key": "YOUR_JELLYFIN_API_KEY",
  "Sources": ["torrentio", "aiostreams"],
  "Versions": [
    [
      "4k",
      "both",
      "en",
      [
        [
          "resolution",
          "preference",
          ">=",
          "2160"
        ]
      ]
    ]
  ]
}
```

Note: If you want to enable Easynews/AIOStreams scraping, set the environment variables `AIOSTREAMS_UUID` and `AIOSTREAMS_B64CONFIG` (see `settings.json.template`).

### Helper scripts & utilities

Several helper scripts and utilities are provided for setup, maintenance, and optional integrations:

- Setup & service helpers (Windows): `setup_venv.ps1`, `install_autostart.bat`, `start_all_services.bat`, `stop_service.bat`, `uninstall_autostart.bat` — use these to create a virtual environment and install/run the service.

- Jellyseerr sync utilities (`jellyseer_sync/`):
  - `trakt_blacklist_sync.py` — sync watched movies from Trakt (API or JSON export) into Jellyseerr's blacklist (optional; requires Trakt credentials or exported JSON).
  - `extract_movies.py` — helper to extract watched movies from Trakt JSON exports for use with the blacklist sync.
  - `blacklist_low_rated.py`, `remove_blacklisted_by_year.py` — convenience scripts to manage blacklists.

- Verification & maintenance: `verify_setup.ps1` (Windows) helps validate your configuration after setup.

Usage notes: These helper scripts are optional and documented in their respective folders (`jellyseer_sync/`, `scripts/`). Run `python jellyseer_sync/trakt_blacklist_sync.py --help` to view usage options for the Trakt sync tool.

 