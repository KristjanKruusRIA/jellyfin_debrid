# Jellyfin_Debrid
Jellyfin torrent downloading through Debrid Services, using Seerr requests and watchlists.

Using content services like Seerr, your personal media server users can add movies/shows to their watchlist and they become available to stream in minutes.

Based on [plex_debrid](https://github.com/itsToggle/plex_debrid)

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

4. Install [Servy](https://github.com/aelassas/servy) for Windows service management:
   ```powershell
   winget install servy
   ```

5. Register as a Windows service (run as Administrator):
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\Install-Service.ps1
   ```

6. Start the service:
   ```bat
   scripts\start_all_services.bat
   ```

The service auto-starts ~3 minutes after boot (delayed start + Docker wait). You can also manage it via `servy-cli start/stop/restart --name=jellyfin-debrid` or the Servy Manager GUI.

Log viewer: http://localhost:7654

**For detailed Windows setup instructions, see [WINDOWS_SETUP.md](WINDOWS_SETUP.md)**

---

### In Action:

![ezgif com-gif-maker](https://user-images.githubusercontent.com/71379623/185643627-45217303-75d8-4c9d-8c8b-41bb2e27fd87.gif)
 
### Description:

A jellyfin_debrid setup consists of three parts.
- The first part is Seerr which allows you to request media
- The second part is a personal media server (e.g., Jellyfin), which allows you to watch these files from anywhere on any device.
- The third part is the jellyfin_debrid script, which ties both things together and provides an easy way to download media content from your debrid service.

The jellyfin_debrid script monitors Seerr requests (and optionally Overseerr) of specified users for newly added movies/shows and newly released episodes of watchlisted shows.

How it works:
- Monitor requests/watchlists from Seerr (default) and Overseerr (optional).
- Scrape torrent indexers and streaming providers for candidate releases using configurable scrapers and version rules.
- Prefer cached releases on supported debrid services; if needed, add torrents to a debrid service and/or download directly.
- Validate downloads (size checks, ranged retries, progress reporting), sanitize and preserve filenames, then move files into organized Movies/Shows folders.
- Trigger a Jellyfin library refresh (full or partial) so new content becomes available for playback.

This workflow enables near-instant availability for cached content and robust, configurable automation for uncached downloads.
 
### Features:
- Cross-platform: works on Windows, macOS, Linux and other Unix-like systems.
- Fast, configurable scanning: default polling interval is every 5 seconds (configurable) to pick up new Seerr requests quickly.
- Sources:
  - Primary: Seerr (requests/watchlists). Overseerr is supported as well.
  - Scrapers: AIOStreams (for Easynews / direct HTTP sources) and Comet (for debrid-cached torrents).
- Debrid integration: supports RealDebrid.
- Download robustness: supports direct HTTP downloads and debrid APIs, temp-file downloads with progress reporting, ranged retries for partial responses, and size validation against expected size.
- Filenames and organization: sanitizes filenames for Windows, preserves extensions (including fixes for certain Easynews URL cases), and organizes files into:
  - Movies/Movie Name (Year)/filename
  - Shows/Show Name/Season XX/filename
- Quality selection: selects best candidate release,
- Integrations: triggers Jellyfin library refreshes after downloads and monitors Seerr for requests.
- Configuration & logging: primary settings in `config/settings.json` (template at `settings.json.template`), and detailed logs are written to `config/jellyfin_debrid.log`.

### Example minimal `settings.json` ✅

Below is a minimal example to get you started with Jellyfin + Seerr + RealDebrid. Replace the placeholder values with your actual API keys and URLs.

```json
{
  "Content Services": ["seerr"],
  "seerr API Key": "YOUR_SEERR_API_KEY",
  "seerr Base URL": "http://seerr.local:5055",
  "Library collection service": "seerr Library",
  "Library update services": ["Seerr Requests"],
  "Debrid Services": ["Real Debrid"],
  "Real Debrid API Key": "YOUR_REALDEBRID_API_KEY",
  "Jellyfin server address": "http://jellyfin.local:8096",
  "Jellyfin API Key": "YOUR_JELLYFIN_API_KEY",
  "Sources": ["aiostreams", "comet"],
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

Note: To enable AIOStreams or Comet scrapers, configure them in your `config/settings.json` file (see Configuration section below).

### Configuration for Scrapers

**Comet Scraper:**
Three Comet instances are available, each pointing to a different server:
- **comet-selfhosted** — your self-hosted Comet instance
- **comet-elfhosted** — ElfHosted Comet (`https://cometnet.elfhosted.com`)
- **comet-base** — any other Comet server

Each instance has its own Base URL and B64Config in `config/settings.json`. Add the instances you want to the `"Sources"` list, then configure their URL and B64Config.

The Comet URL format is: `https://<host>/{BASE64_CONFIG}/manifest.json`

To extract the BASE64_CONFIG from your Comet URL:
1. Get your Comet configuration URL (includes your debrid API key and preferences)
2. Extract the base64 string between the domain and `/manifest.json`
3. Add it to your `config/settings.json`

Example settings.json entries:
```json
"Sources": ["aiostreams", "comet-selfhosted", "comet-elfhosted"],
"Comet Selfhosted Base URL": "http://your-server:8000",
"Comet Selfhosted B64Config": "eyJ...",
"Comet Elfhosted Base URL": "https://cometnet.elfhosted.com",
"Comet Elfhosted B64Config": "eyJ..."
```

**AIOStreams Scraper:**
For AIOStreams (Easynews), add both UUID and B64Config to your `config/settings.json`:
```json
"AIOStreams UUID": "your-uuid-here",
"AIOStreams B64Config": "your-base64-config-here"
```

### Helper scripts & utilities

Several helper scripts and utilities are provided for setup, maintenance, and optional integrations:

- **Service management (Windows, requires [Servy](https://github.com/aelassas/servy)):**
  - `scripts/Install-Service.ps1` — registers jellyfin-debrid as a Windows service (run as Administrator)
  - `scripts/Uninstall-Service.ps1` — removes the service
  - `scripts/start_all_services.bat` — start the service
  - `scripts/stop_service.bat` — stop the service
  - `scripts/restart_service.bat` — restart the service

- Setup: `setup_venv.ps1` — creates the Python virtual environment.

- Seerr sync utilities (`seerr_sync/`):
  - `trakt_blacklist_sync.py` — sync watched movies from Trakt (API or JSON export) into Seerr's blacklist (optional; requires Trakt credentials or exported JSON).
  - `extract_movies.py` — helper to extract watched movies from Trakt JSON exports for use with the blacklist sync.
  - `blacklist_low_rated.py`, `remove_blacklisted_by_year.py` — convenience scripts to manage blacklists.

- Verification & maintenance: `verify_setup.ps1` (Windows) helps validate your configuration after setup.

Usage notes: These helper scripts are optional and documented in their respective folders (`seerr_sync/`, `scripts/`). Run `python seerr_sync/trakt_blacklist_sync.py --help` to view usage options for the Trakt sync tool.

Developer / contributors: To enable local linting, formatting and pre-commit hooks, install dev dependencies and enable pre-commit:

```bash
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pre-commit install
pre-commit run --all-files
```

The repository includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that runs Ruff, Black, isort, mypy and pytest on each push/PR.

 
