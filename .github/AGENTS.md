# Jellyfin_Debrid — Project Guidelines

## Architecture

Windows-first Python 3.10+ automation system. Monitors Seerr requests, scrapes torrent sources via pluggable scrapers, checks debrid caching, downloads content locally, and triggers Jellyfin library refreshes.

```
Seerr Requests → Scraper Services → Debrid Cache Check → Downloader → File Organization → Jellyfin Refresh
```

## Module Map

| Module | Purpose | Key Files |
|--------|---------|-----------|
| `main.py` | Entry point — delegates to `ui.run()` | — |
| `frontend.py` / `frontend_jobs.py` | Flask routes for logs/search/manual scrape/download APIs plus in-memory scrape-job registry and safe release serialization for browser-facing APIs | `frontend.py`, `frontend_jobs.py` |
| `ui/` | Interactive CLI, logging (`ui_print()`), settings UI | `ui_print.py`, `ui_settings.py` |
| `content/` | Media classes (movie/show/season/episode), Seerr integration, TMDB manual hydration adapter | `classes.py`, `services/seerr.py`, `services/manual_media.py` |
| `scraper/` | Pluggable scraper services (AIOStreams, Comet) | `services/__init__.py`, `services/aiostreams.py`, `services/comet.py` |
| `debrid/` | Debrid provider integrations (RealDebrid) | `services/__init__.py`, `services/realdebrid.py` |
| `releases/` | Release model, quality/version selection, scoring/sorting rules | `__init__.py` |
| `downloader/` | HTTP download with progress, Windows filename sanitization, file organization | `__init__.py` |
| `settings/` | Configuration management, settings registry, `setting` class | `__init__.py` |
| `store/` | Pickle-based caching (`store.load` / `store.save`) | `__init__.py` |
| `base/` | Shared utilities, re-exported stdlib modules, `custom_session` | `__init__.py` |
| `config/` | Runtime config: `settings.json`, log file | `settings.json` (from `settings.json.template`) |

## Service Pattern

All service modules in `content/services/`, `scraper/services/`, `debrid/services/` follow this contract:

```python
name = "service_name"          # Module-level string identifier
def setup(cls, new=False): ... # Interactive configuration
# Service-specific API methods (scrape, check, download, etc.)
```

Services are registered in their parent `__init__.py` (e.g., `scraper/services/__init__.py` builds the `scrapers` list). Settings are declared in `settings/settings_list`.

## Code Style

- **Black** formatter, 88 char line length (see `pyproject.toml`)
- **isort** with black profile
- **ruff** for linting
- **mypy** with `ignore_missing_imports = true`; excludes `tests/`, `debug_*.py`, `seerr_sync/`
- **Regex**: Use `regex` module (not `re`), VERSION1 default (set in `base/__init__.py`)
- **Type hints**: Use where possible

## Critical Conventions

### Logging — Never use `print()` in services
```python
from ui.ui_print import ui_print, ui_settings
ui_print("[module_name] message", debug=ui_settings.debug)  # Debug-gated
ui_print("[module_name] always visible message")             # Always shown
```
Logs go to `config/jellyfin_debrid.log`. Debug messages must include module prefix in brackets.

### Filename Sanitization — Windows required
All filenames **must** pass through `downloader.sanitize_filename()` which strips `< > : " / \ | ? *` and replaces slashes with dots. File organization: `Movies/{Title} ({Year})/`, `Shows/{Title}/Season {XX}/`.

### Configuration
- Primary config: `config/settings.json` (template: `settings.json.template`)
- Settings accessed via **module-level variables** on service modules (e.g., `realdebrid.api_key`)
- Scraper configs use **base64-encoded strings** (AIOStreams UUID/B64Config, Comet B64Config)

### Release Version System
Versions in `settings.json` define structured quality criteria. `releases.sort` applies rules (requirement/preference) and triggers to filter and rank releases. Version selection is multi-pass: tries highest quality first, falls back if no cached results.

## API Integration Reference

| Service | Base URL | Auth | Key Status Codes |
|---------|----------|------|-----------------|
| Frontend (Flask manual search) | `http://localhost:7654/` | None | `POST /api/scrapes` → 202 running, `GET /api/scrapes/<job_id>` → 200/404, `POST /api/scrapes/<job_id>/downloads` → 200 started / structured 4xx/5xx errors |
| Seerr | `{base_url}/api/v1/` | `X-Api-Key` header | 1=Pending, 2=Approved, 3=Declined, 4=Processing, 5=Available |
| RealDebrid | `api.real-debrid.com/rest/1.0/` | `Bearer` token | 202=already done, 403=permission denied/premium, 401=bad key |
| AIOStreams | `{base_url}/stremio/{uuid}/{b64config}/` | Embedded in URL | Stremio addon format |
| Comet | `{base_url}/{b64config}/` | Embedded in URL | Stremio addon format |

### Frontend Manual Search API Notes

- `GET /api/search?q=<query>[&type=movie|tv|all]` returns TMDB-backed JSON results for the `/search` page.
- Manual scrape/download endpoints are designed to work without Seerr configuration.
- Scrape jobs are stored in memory (`frontend_jobs.JobRegistry`) and are not persisted across process restarts.

### Server-side Release State Convention

- Keep full release objects server-side in `frontend_jobs.JobRegistry`.
- Browser responses must use safe release summaries (`serialize_release` / `serialize_releases`) with opaque `release_id` indices.
- Never expose raw release internals in frontend API payloads (e.g., direct `download` URLs, hashes, or raw file payload structures).

## Build & Test

```powershell
# Setup (Windows)
.\setup_venv.ps1
.\venv\Scripts\Activate.ps1

# Run
python main.py                          # Interactive
python main.py --config-dir ./config    # Custom config
python main.py -service                 # Service mode

# Test & Lint
pip install -r requirements-dev.txt
pytest                                  # Run tests
black . ; isort . ; ruff check --fix . ; mypy .
```

Pre-commit hooks configured in `.pre-commit-config.yaml` (black, isort, ruff, mypy).

## Common Tasks

### Adding a New Scraper
1. Create `scraper/services/newscraper.py` following the service pattern above
2. Implement `scrape(query, altquery)` → returns `list[releases.release]`
3. Register in `scraper/services/__init__.py` (import + add to `scrapers`/`active_default`)
4. Add settings to `settings/settings_list` if needed
5. Add service name to `Sources` in `settings.json.template`

### Adding a New Debrid Provider
1. Create `debrid/services/newprovider.py` with `check(element)` and `download(element)` methods
2. Register in `debrid/services/__init__.py`
3. Add API key setting to `settings/settings_list`

### Download Flow
1. Scraper returns `releases.release` objects with `download` URLs and `type` (magnet/http)
2. `debrid.check()` verifies cache status, populates `release.files` and `release.cached`
3. `debrid.download()` unrestricts links or adds magnets, calls `downloader.download_from_realdebrid()`
4. `downloader.download_file()` streams to `.downloading/` temp dir, validates size, moves to final path
5. Jellyfin library refresh + Seerr status update triggered on success

### Persistence
```python
import store
cache = store.load("module_name", "variable_name")   # Load pickle
store.save(data, "module_name", "variable_name")       # Save pickle
# Files stored as {config_dir}/{module}_{variable}.pkl
```

## Key Data Types

- **`releases.release`**: Core release object — `source`, `type` (magnet/http), `title`, `files`, `size`, `download`, `hash`, `cached`, `resolution`, `seeders`
- **`content.classes.media`**: Base media object — extended by `seerr.movie`, `seerr.show`; has `EID`, `type`, `title`, `Seasons`/`Episodes` for shows
- **`releases.sort.version`**: Quality version — `name`, `triggers`, `lang`, `rules`; applied via `releases.sort(scraped_releases, version)`

## Self-Improvement & Learnings (`.learnings/`)

Agents use the **self-improving-agent** skill to log errors, corrections, and insights during development. This creates a feedback loop that improves future tasks.

### Files
| File | Purpose |
|------|---------|
| `.learnings/LEARNINGS.md` | Corrections, insights, knowledge gaps, best practices |
| `.learnings/ERRORS.md` | Command failures, exceptions, unexpected behavior |
| `.learnings/FEATURE_REQUESTS.md` | Capabilities requested or identified during work |
| `.learnings/examples.md` | Reference examples for entry formatting |

### When to Log
- **Command/operation fails** → `ERRORS.md`
- **User corrects the agent** → `LEARNINGS.md` (category: `correction`)
- **Knowledge was outdated or wrong** → `LEARNINGS.md` (category: `knowledge_gap`)
- **Better approach discovered** → `LEARNINGS.md` (category: `best_practice`)
- **User wants a missing capability** → `FEATURE_REQUESTS.md`

### Promotion
When a learning is broadly applicable, **promote** it:
- To **this file** (`AGENTS.md`) if it affects agent workflows or project conventions.
- To `/memories/repo/` if it's a codebase fact useful for future tasks.
- Mark the original entry `**Status**: promoted`.

### Review
Agents should review `.learnings/` before starting major tasks to avoid repeating past mistakes.

## Memory & Documentation Maintenance

**Agents must keep memory and this file up to date as the project evolves.**

### Repository Memory (`/memories/repo/`)
- After completing any task that adds, removes, or changes modules, services, settings, data types, APIs, or conventions, **store the key facts** in `/memories/repo/` using the memory tool's `create` command.
- Facts to store: new module purposes, new service contracts, changed API endpoints, new settings keys, new data types or fields, new build/test commands, and any discovered conventions not yet documented.
- Each fact should include `subject`, `fact`, `citations` (file paths), `reason`, and `category`.

### Updating This File (`AGENTS.md`)
Whenever a task results in any of the following, **update the relevant section of this file before the phase is considered complete**:
- **New module or service added** → Update the **Module Map** table and/or **Service Pattern** section.
- **New scraper or debrid provider** → Update **Common Tasks** with any new steps and **API Integration Reference** if applicable.
- **New data type or key field change** → Update **Key Data Types**.
- **New setting or config change** → Update **Configuration** and/or **Build & Test** sections.
- **New convention or code style rule** → Update **Code Style** or **Critical Conventions**.
- **New script or automation** → Update **Windows-Specific Notes** or **Build & Test**.
- **Workspace structure change** → Ensure the **Module Map** still reflects reality.

This ensures future agents always have accurate, current context about the project.

## Windows-Specific Notes

- Use PowerShell scripts (`.ps1`) for automation
- Path handling: raw strings `r"E:\Path"` or forward slashes
- Default download path: `E:\Media` (override with `DOWNLOAD_PATH` env var)
- Service autostart via `scripts/install_autostart.bat` (requires admin)
