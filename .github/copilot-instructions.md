# Jellyfin_Debrid AI Coding Guidelines

## Architecture Overview

This is a **Windows-first Python 3.10+ automation system** that monitors Jellyseerr requests, scrapes torrent sources, checks debrid caching, downloads content, and triggers Jellyfin library refreshes.

### Core Data Flow
```
Jellyseerr Requests → Scraper Services → Debrid Cache Check → Downloader → File Organization → Jellyfin Refresh
```

### Module Responsibilities
- **`ui/`**: Interactive CLI and logging (`ui_print()` for all output, respects debug levels)
- **`content/`**: Media classes (movies/shows), Jellyseerr/Overseerr integration
- **`scraper/`**: Pluggable scraper services (Torrentio, AIOStreams, Comet)
- **`debrid/`**: Debrid provider integrations (RealDebrid primary)
- **`releases/`**: Quality/version selection logic, release scoring
- **`downloader/`**: HTTP download with progress tracking, Windows filename sanitization
- **`settings/`**: Configuration management, settings registry
- **`store/`**: Pickle-based caching for persistent state
- **`base/`**: Shared utilities, re-exported standard library modules

## Critical Conventions

### Service Pattern
All service modules (`content/services/`, `scraper/services/`, `debrid/services/`) follow this pattern:
- Class/module variable `name` (string identifier)
- `setup(cls, new=False)` method for configuration
- Service-specific API methods
- Settings registered in `settings/settings_list`

**Example**: See [scraper/services/aiostreams.py](../scraper/services/aiostreams.py) for scraper pattern, [debrid/services/realdebrid.py](../debrid/services/realdebrid.py) for debrid pattern.

### Configuration System
- Primary config: `config/settings.json` (template at [settings.json.template](../settings.json.template))
- Settings accessed via **class variables** on service modules (e.g., `realdebrid.api_key`)
- Settings modified through `ui_settings` or direct JSON editing
- Scraper configs use **base64-encoded strings** (AIOStreams UUID/B64Config, Comet B64Config)

### Logging & Output
- **Always use `ui_print()`** from [ui/ui_print.py](../ui/ui_print.py), never raw `print()` in services
- Format: `ui_print("[module] message", debug=ui_settings.debug)` or `debug="true"`
- Logs written to `config/jellyfin_debrid.log` (set by `set_log_dir()`)
- Debug messages should include module prefix: `[realdebrid]`, `[aiostreams]`, `[downloader]`

### Filename Handling
- **Must sanitize for Windows**: remove `< > : " / \ | ? *`, replace slashes with dots
- See `sanitize_filename()` in [downloader/__init__.py](../downloader/__init__.py) (lines 28-47)
- File organization: `Movies/{Title} ({Year})/`, `Shows/{Title}/Season {XX}/`
- Preserve file extensions, handle Easynews URL edge cases

### Release Version System
Versions defined in `settings.json` as structured criteria with quality preferences:
```json
["4k", "both", "en", [["resolution", "preference", ">=", "2160"]]]
```
- See [releases/__init__.py](../releases/__init__.py) for scoring/sorting logic
- Version selection is **multi-pass**: tries highest quality first, falls back if no cached results

## Development Workflows

### Setup & Running
```powershell
# Initial setup (Windows)
.\setup_venv.ps1

# Activate venv
.\venv\Scripts\Activate.ps1

# Run main application
python main.py

# Run with custom config directory
python main.py --config-dir ./config

# Run in service mode
python main.py -service
```

### Testing & Linting
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Manual linting (or use pre-commit)
black .
isort .
ruff check --fix .
mypy .
```

**Pre-commit**: Configured in [.pre-commit-config.yaml](../.pre-commit-config.yaml) with black, isort, ruff, mypy. Excludes `tests/`, `debug_*.py`, `jellyseer_sync/` from mypy.

### Code Style
- **Black formatter**: 88 char line length (see [pyproject.toml](../pyproject.toml))
- **isort**: black profile
- **Type hints**: Use where possible (mypy check with `ignore_missing_imports = true`)
- **Regex**: Use `regex` module (not `re`), default to VERSION1 (set in [base/__init__.py](../base/__init__.py) line 23)

## External Integration Points

### API Patterns
- **Jellyseerr**: REST API at `{base_url}/api/v1/`, auth via `X-Api-Key` header
  - Request statuses: 1=Pending, 2=Approved, 3=Declined, 4=Processing, 5=Available
  - See [content/services/jellyseerr.py](../content/services/jellyseerr.py)

- **RealDebrid**: API at `api.real-debrid.com/rest/1.0/`, auth via `Bearer` token
  - Error codes: 202=already done, 400=bad request, 403=permission denied/premium required
  - See [debrid/services/realdebrid.py](../debrid/services/realdebrid.py)

- **Scrapers**: HTTP-based with service-specific URL patterns
  - Torrentio: Stremio addon format
  - AIOStreams: Requires UUID + B64Config for Easynews integration
  - Comet: Requires B64Config with debrid API keys embedded

### Configuration Secrets
AIOStreams and Comet use **base64-encoded configuration strings** (not just API keys). Extract from Stremio URLs:
- AIOStreams: `https://aiostreamsfortheweebs.midnightignite.me/{UUID}/{B64CONFIG}/manifest.json`
- Comet: `https://cometnet.elfhosted.com/{B64CONFIG}/manifest.json`

## Common Patterns

### Adding a New Scraper
1. Create `scraper/services/newscraper.py`
2. Define module variables: `name`, session config
3. Implement `setup(cls, new=False)` and `scrape(query, altquery)`
4. Return list of `releases.release` objects
5. Register settings in `settings/settings_list` if needed
6. Add to `scraper/services/__init__.py` imports
7. Add service name to `Sources` in settings.json

### Download Flow
1. Scraper returns releases with `download` URLs
2. Debrid service checks cache, adds torrent if needed, returns direct link
3. `downloader.download_file()` handles HTTP download to temp dir
4. Validates size (if `expected_size` provided), logs diagnostics for small/failed downloads
5. Moves from `.downloading/` temp to final `Movies/` or `Shows/` location
6. Jellyfin library refresh triggered

### Persistence
Use `store.load(module, variable)` and `store.save(cache, module, variable)` for caching:
- Stores Python objects as pickle files in config dir
- Naming: `{config_dir}/{module}_{variable}.pkl`
- Example: Jellyseerr request cache, ignored media list

## Windows-Specific Considerations
- Use PowerShell scripts (`.ps1`) for automation
- Service installation via `scripts/install_autostart.bat` (requires admin)
- Path handling: Use raw strings `r"E:\Path"` or forward slashes
- Default download path: `E:\Media` (override with `DOWNLOAD_PATH` env var)

## Available Skills (AI Agent Capabilities)

This workspace has specialized skills that provide domain-specific expertise. Skills are automatically activated when you describe tasks in their domain, or you can explicitly reference them by name.

### Version Control & GitHub
- **`git-commit`**: Intelligent git commits with conventional commit messages
  - Triggers: "commit changes", "create a commit", "/commit"
  - Auto-detects type/scope from diff, generates descriptive messages
- **`github-issues`**: Create and manage GitHub issues
  - Triggers: "create an issue", "file a bug", "request a feature"
  - Handles labels, assignees, milestones, and issue workflows
- **`gh-cli`**: Comprehensive GitHub CLI reference
  - Use for repos, PRs, Actions, projects, releases, gists, codespaces
- **`make-repo-contribution`**: Ensure contributions follow repository guidelines
  - Triggers: Before filing issues, creating branches, or making PRs

### Code Quality & Documentation
- **`refactor`**: Surgical code refactoring to improve maintainability
  - Use for extracting functions, improving type safety, eliminating code smells
  - Less drastic than full rewrites; focus on gradual improvements
- **`excalidraw-diagram-generator`**: Generate architecture diagrams from descriptions
  - Triggers: "create a diagram", "visualize the architecture", "draw a flowchart"
  - Outputs `.excalidraw` JSON files for system architecture and data flows
- **`markdown-to-html`**: Convert markdown files to HTML
  - Useful for documentation generation and web templates

### Testing & Validation
- **`webapp-testing`**: Interact with and test web applications using Playwright
  - Use for verifying frontend functionality, debugging UI, capturing screenshots
- **`web-design-reviewer`**: Visual inspection of websites to identify design issues
  - Triggers: "review website design", "check the UI", "fix the layout"

### Project Management
- **`prd`**: Generate Product Requirements Documents
  - Creates executive summaries, user stories, technical specs, and risk analysis
- **`meeting-minutes`**: Generate concise, actionable meeting minutes
  - Includes metadata, attendees, decisions, and action items with owners/due dates

### How to Use Skills
**Natural language**: Simply describe what you need in the skill's domain
```
"Create a diagram showing how the scraper services interact with the debrid API"
→ Activates excalidraw-diagram-generator skill

"Commit the changes to the downloader module"
→ Activates git-commit skill with conventional commit format
```

**Explicit reference**: Mention the skill name directly
```
"Use the refactor skill to improve the release scoring logic"
"Apply the github-issues skill to file a bug report"
```

**Note**: Skills load their full instructions automatically when activated, providing specialized guidance beyond these general coding guidelines.

## Available Skills (AI Agent Capabilities)

This workspace has specialized skills that provide domain-specific expertise. Skills are automatically activated when you describe tasks in their domain, or you can explicitly reference them by name.

### Version Control & GitHub
- **`git-commit`**: Intelligent git commits with conventional commit messages
  - Triggers: "commit changes", "create a commit", "/commit"
  - Auto-detects type/scope from diff, generates descriptive messages
- **`github-issues`**: Create and manage GitHub issues
  - Triggers: "create an issue", "file a bug", "request a feature"
  - Handles labels, assignees, milestones, and issue workflows
- **`gh-cli`**: Comprehensive GitHub CLI reference
  - Use for repos, PRs, Actions, projects, releases, gists, codespaces
- **`make-repo-contribution`**: Ensure contributions follow repository guidelines
  - Triggers: Before filing issues, creating branches, or making PRs

### Code Quality & Documentation
- **`refactor`**: Surgical code refactoring to improve maintainability
  - Use for extracting functions, improving type safety, eliminating code smells
  - Less drastic than full rewrites; focus on gradual improvements
- **`excalidraw-diagram-generator`**: Generate architecture diagrams from descriptions
  - Triggers: "create a diagram", "visualize the architecture", "draw a flowchart"
  - Outputs `.excalidraw` JSON files for system architecture and data flows
- **`markdown-to-html`**: Convert markdown files to HTML
  - Useful for documentation generation and web templates

### Testing & Validation
- **`webapp-testing`**: Interact with and test web applications using Playwright
  - Use for verifying frontend functionality, debugging UI, capturing screenshots
- **`web-design-reviewer`**: Visual inspection of websites to identify design issues
  - Triggers: "review website design", "check the UI", "fix the layout"

### Project Management
- **`prd`**: Generate Product Requirements Documents
  - Creates executive summaries, user stories, technical specs, and risk analysis
- **`meeting-minutes`**: Generate concise, actionable meeting minutes
  - Includes metadata, attendees, decisions, and action items with owners/due dates

### How to Use Skills
**Natural language**: Simply describe what you need in the skill's domain
```
"Create a diagram showing how the scraper services interact with the debrid API"
→ Activates excalidraw-diagram-generator skill

"Commit the changes to the downloader module"
→ Activates git-commit skill with conventional commit format
```

**Explicit reference**: Mention the skill name directly
```
"Use the refactor skill to improve the release scoring logic"
"Apply the github-issues skill to file a bug report"
```

**Note**: Skills load their full instructions automatically when activated, providing specialized guidance beyond these general coding guidelines.
