# Backend Code Cleanup Guide

This document maps every backend module, function, debug log, failover mechanism, and sleep/retry pattern added during development. Use it to identify what can be safely removed or simplified now that the system is working as expected.

---

## Table of Contents

1. [debrid/services/realdebrid.py](#debridservicesrealdebridpy)
2. [downloader/__init__.py](#downloaderinit__py)
3. [content/classes.py](#contentclassespy)
4. [scraper/services/aiostreams.py](#scraperservicesaiostreamspy)
5. [scraper/services/comet.py](#scraperservicescometpy)
6. [frontend.py & frontend_jobs.py](#frontendpy--frontend_jobspy)
7. [Other Modules](#other-modules)
8. [Cleanup Priority Matrix](#cleanup-priority-matrix)

---

## debrid/services/realdebrid.py

The largest and most complex module. Contains the RD API integration with two main flows: `check()` (mark releases as cached) and `download()` (resolve + download).

### Module-Level

| Line | Item | Type | Notes |
|------|------|------|-------|
| 11-16 | `try: import rd_downloader` | Failover | Sets `has_rd_downloader` flag. Can remove if `rd_downloader` module is never used. |
| 23 | `requests.Session()` | Core | Keep |
| 24-30 | `errors` list | Core | HTTP status to error description mapping. Keep |

### Functions

#### `setup(cls, new=False)` — Lines 33-36
- **Purpose:** Configures RD API key via CLI
- **Cleanup:** None needed

#### `logerror(response, context=None)` — Lines 40-70
- **Purpose:** Logs HTTP error codes from RD API
- **Cleanup:** None needed — this is production error handling

#### `get(url, context=None)` — Lines 74-93
- **Purpose:** GET wrapper, returns SimpleNamespace
- **Debug logging:** Line 87 — `[realdebrid] error: (json exception): {e}` — **Keep** (real error)
- **Cleanup:** None needed

#### `post(url, data, context=None)` — Lines 97-128
- **Purpose:** POST wrapper
- **Debug logging:** Lines 113/121 — json exception with context — **Keep**
- **Cleanup:** None needed

#### `delete(url, context=None)` — Lines 132-152
- **Purpose:** DELETE wrapper
- **Debug logging:** Line 143 — delete exception — **Keep**
- **Cleanup:** None needed

#### `download(element, stream=True, query="", force=False)` — Lines 156-850+
This is the **main cleanup target**. It handles HTTP releases, magnet releases, cached/uncached torrents, file selection, polling, and post-download actions.

##### Debug Logging (candidates for removal)

| Line | Message | Verdict |
|------|---------|---------|
| ~206 | `[realdebrid] debug: checking release: {title} \| type= \| is_http: \| download[0]:` | **REMOVE** — verbose per-release debug for HTTP detection. Was used to debug type detection. |
| ~221 | `[realdebrid] processing http stream link: {title}` | **SIMPLIFY** — useful but redundant with download confirmation |
| ~225 | `[realdebrid] http download url: {url}...` | **REMOVE** — exposes raw URLs in logs, only needed for debugging |
| ~230 | `[realdebrid] http release ready for download: {title}` | **REMOVE** — redundant with "processing http stream link" |
| ~248 | `[realdebrid] debug: checking if "{download_id}" is in downloading list (len=...): {list}` | **REMOVE** — temporary debug for downloading list tracking |
| ~283 | `[realdebrid] no file info available (nodownloadlinks enabled), adding magnet to RD...` | **KEEP** — informational about magnet flow |
| ~329 | `[realdebrid] magnet added, torrent_id: {id}` | **KEEP** — useful operational log |
| ~337 | `[realdebrid] torrent status: {status}` | **KEEP** — useful |
| ~350 | `[realdebrid] updated status: {status} (poll N/5)` | **SIMPLIFY** — could log only final status |
| ~530 | `[realdebrid] debug: got link for video file: {filename}` | **REMOVE** — per-file verbose debug |
| ~590 | `[realdebrid] debug: filenames from RD unrestrict: {filenames}` | **REMOVE** — raw data dump |
| ~595 | `[realdebrid] debug: download links: {links}` | **REMOVE** — raw URL dump |
| ~710 | `[realdebrid] traceback: {traceback}` | **SIMPLIFY** — keep error message, remove full traceback in production |
| ~810 | `[realdebrid] debug: checking if "{download_id}" is in downloading list` (uncached path) | **REMOVE** — same debug pattern duplicated |
| ~815 | `[realdebrid] warning: download_id "{id}" not found in downloading list: {list}` | **REMOVE** — only needed during development |

##### Failover / Fallback Logic

| Lines | Pattern | Description | Verdict |
|-------|---------|-------------|---------|
| ~166-173 | `alternative_query` for episodes | Creates `S{NN}` pattern to match season packs for episode downloads | **KEEP** — this is correct behavior, not a failover |
| ~177-187 | HTTP release detection | Checks `release.type == "http"` AND `download[0].startswith("http")` | **SIMPLIFY** — the double-check (`type` attr + URL prefix) was added to catch edge cases. Now that scrapers set `type="http"` properly, the URL prefix check is redundant |
| ~310-380 | Magnet addMagnet path with HTTP URL fallback | If magnet_candidate starts with `http://`, re-routes to HTTP download instead of adding as magnet | **REMOVE** — This entire "HTTP URL found in addMagnet path" branch was a safety net for when scrapers didn't set `type="http"` properly. Scrapers now set it correctly so HTTP releases never reach this path. |
| ~340-362 | Polling loop (5×2s) after selectFiles | Polls `torrents/info/` up to 5 times waiting for `downloaded` status | **KEEP** — necessary for cached torrents that need a moment after file selection |
| ~660-670 | Uncached torrent keepalive | Keeps torrent if version allows uncached and status is downloading/queued | **REVIEW** — if you only want cached downloads, this entire uncached branch can be removed |
| ~730-850 | Uncached download branch (`stream=False`) | Full duplicate of the magnet flow but for uncached torrents, including another HTTP URL fallback | **REMOVE IF CACHED-ONLY** — the entire `else` (uncached) branch mirrors the cached branch with its own HTTP URL fallback. If you only use cached downloads, remove the entire uncached path. |

##### Duplicated Code Blocks

| Pattern | Locations | Issue |
|---------|-----------|-------|
| Jellyfin + Seerr library refresh after download | Lines ~258-276, ~360-378, ~630-648, ~820-838 | **4 copies** of the same try/except jellyfin.refresh + seerr.refresh block. Should be extracted to a helper function. |
| `import debrid as db` + downloading list removal | Lines ~242-260, ~340-360, ~800-820 | **3 copies** of the same download_id construction and db.downloading.remove pattern. Extract to helper. |
| HTTP URL detection in magnet path | Lines ~310-380 (cached), ~760-790 (uncached) | **2 copies** of "looks like HTTP URL in addMagnet path" fallback. If scrapers properly tag HTTP releases, both can be removed. |

##### Sleep Calls

| Line | Duration | Purpose | Verdict |
|------|----------|---------|---------|
| ~333 | `time.sleep(2)` | Wait for RD to process magnet | **KEEP** — RD needs time |
| ~341 | `time.sleep(2)` × 5 polls | Poll loop after selectFiles | **KEEP** — necessary for cached torrents |
| ~609 | `time.sleep(0.1)` | Before selectFiles on uncached | **REMOVE IF CACHED-ONLY** |

#### `check(element, force=False)` — Lines 865-900
- **Purpose:** Marks all releases as cached (scraper pre-verified)
- **Recent fix:** Removed per-release "skipping hash check" spam, replaced with single summary
- **Cleanup:** Clean. No further action needed.

#### `account_info()` — Lines 905-930
- **Purpose:** Diagnostic — fetch RD account info
- **Cleanup:** Could be removed if not used in production. Useful for debugging only.

#### `torrents_list(limit=50)` — Lines 935-970
- **Purpose:** Diagnostic — list active RD torrents
- **Cleanup:** Could be removed if not used in production. Useful for debugging only.

---

## downloader/__init__.py

Manages local file downloads via HTTP streaming with temp files and file organization.

### Functions

#### `sanitize_filename(filename)` — Lines 25-41
- **Cleanup:** None — core functionality

#### `download_file(url, filename, is_show, expected_size, element)` — Lines 44-232
##### Debug Logging

| Line | Message | Verdict |
|------|---------|---------|
| ~53 | `[downloader] Starting download: {filename}` | **KEEP** |
| ~83 | `[downloader] HTTP status: {status}; Content-Length: {len}; Content-Type: {type}` | **SIMPLIFY** — useful but verbose. Could be debug-only |
| ~111 | `[downloader] Progress: {MB}/{TotalMB} ({percent}%)` | **KEEP** — progress reporting every 500MB is reasonable |
| ~127 | `[downloader] Error: downloaded 0 bytes for URL: {url}` | **KEEP** — real error |
| ~133 | `[downloader] Response snippet (first 2KB): {snippet}` | **REMOVE** — debug forensics for 0-byte downloads. Problem is solved. |
| ~148 | `[downloader] Warning: small download size ({bytes} bytes)` | **SIMPLIFY** — downgrade to debug-only |
| ~153 | `[downloader] Small response snippet (first 2KB): {snippet}` | **REMOVE** — raw binary dump was for debugging small files |
| ~161 | `[downloader] Warning: content-type does not look like a video file` | **KEEP** — legitimate warning |
| ~170 | `[downloader] Attempting ranged retry (Range: bytes=0-)` | **REMOVE** with ranged retry logic (see below) |
| ~183 | `[downloader] Range HTTP status: {status}; Content-Length:...` | **REMOVE** with ranged retry |
| ~195 | `[downloader] Ranged request downloaded {bytes} bytes` | **REMOVE** with ranged retry |
| ~219 | `[downloader] Download complete: {size} - {filename}` | **KEEP** |

##### Failover Logic

| Lines | Pattern | Description | Verdict |
|-------|---------|-------------|---------|
| ~56-67 | Old temp file cleanup | Removes temp files older than 1 hour | **KEEP** — prevents orphan files |
| ~147-200 | Ranged retry for small files (<5MB) | If download is <5MB and content-type is "video", retries with `Range: bytes=0-` header | **REMOVE** — This was added to handle a specific CDN issue that returned truncated responses. If downloads work correctly now, this entire small-file detection + ranged retry block can be removed. |
| ~204-220 | Size validation against expected_size | Discards file if size differs by >5% or >10MB from expected | **KEEP** — legitimate safety check to prevent corrupt downloads |

#### `parse_filename(filename)` — Lines 235-296
- **Cleanup:** None — core utility

#### `get_quality_score(quality_str)` — Lines 299-310
- **Cleanup:** None

#### `is_video_file(filename)` — Lines 313-356
- **Cleanup:** The regex fallback for extensionless files (lines 347-353) was added for AIOStreams HTTP releases. **KEEP** if you still use HTTP-type releases.

#### `is_archive_or_unsafe(filename)` — Lines 359-391
- **Cleanup:** None

#### `select_best_file(files_list)` — Lines 394-444
- **Debug logging:** Line 414 — warning for no video files, Line 437 — selected file info
- **Cleanup:** Both are useful. Keep.

#### `organize_path(filename, is_show, element)` — Lines 447-530
- **Cleanup:** None — recently fixed to accept `element` parameter

#### `download_from_realdebrid(release, element)` — Lines 533-700
##### Debug Logging

| Line | Message | Verdict |
|------|---------|---------|
| ~550 | `[downloader] Processing element type: {type} (is_show: {bool})` | **REMOVE** — diagnostic during development |
| ~640 | `[downloader] Queuing file: {name} (Quality: ..., Size: ...)` | **SIMPLIFY** — useful but verbose for multi-file downloads |

- **Cleanup:** This function is clean. The main flow (detect show/movie → select files → download) is straightforward.

---

## content/classes.py

Contains the `media` class with download orchestration, retry logic, and season pack handling.

### Key Download Methods

#### `media.download(retries=0, library=[], parentReleases=[])` — Lines ~1354-1845
- **Purpose:** Orchestrates scrape → check → download flow
- **Failover:** Alternate year scraping for movies (year±1). **KEEP** — handles metadata year mismatches.
- **Season pack priority:** Exhausts all season packs before individual episodes. **KEEP** — core feature.
- **Cleanup:** Mostly clean. The `parentReleases` inheritance is essential for avoiding redundant scraping.

#### `media.debrid_download(force=False)` — Lines ~1883-1959
- **Purpose:** Passes media object to debrid provider
- **Key pattern:** try/except with `continue` around individual release downloads (lines 1928-1934)
- **Cleanup:** Clean. The try/except per-release is the established error isolation pattern.

#### `media.watch() / unwatch() / watched()` — Lines ~1238-1296
- **Purpose:** Retry tracking with cooldown timers
- **Cleanup:** Core retry system. Keep.

#### `media.season_pack(releases)` — Lines ~2004-2030
- **Purpose:** Decides season pack vs episode based on quality comparison
- **Cleanup:** Clean.

---

## scraper/services/aiostreams.py

### `scrape(query, altquery)` — Lines 75-430

##### Debug Logging (candidates for removal)

| Line | Message | Verdict |
|------|---------|---------|
| ~78 | `[aiostreams] debug: scrape called...` | **REMOVE** — routine entry |
| ~90 | `[aiostreams] debug: UUID and B64Config loaded successfully` | **REMOVE** — startup confirmation |
| ~95 | `[aiostreams] debug: aiostreams not in active scrapers` | **KEEP** — explains why scraping was skipped |
| ~100 | `[aiostreams] debug: aiostreams is active, proceeding` | **REMOVE** — redundant |
| ~179 | `[aiostreams] debug: querying movie API...` | **REMOVE** — routine |
| ~182 | `[aiostreams] debug: movie response...` | **REMOVE** — data dump |
| ~228 | `[aiostreams] debug: found X streams` | **KEEP** — useful count |
| ~247 | `[aiostreams] debug: extracted torrent hash...` | **REMOVE** — per-stream verbose |
| ~337 | `[aiostreams] debug: stream X filename...` | **REMOVE** — per-stream verbose |
| ~359 | `[aiostreams] debug: stream X size from API...` | **REMOVE** — per-stream verbose |
| ~397 | `[aiostreams] debug: converted season pack...` | **REMOVE** — per-stream verbose |
| ~420 | `[aiostreams] debug: added release...` | **REMOVE** — per-stream verbose |

##### Failover Logic

| Lines | Pattern | Verdict |
|-------|---------|---------|
| ~119-166 | TMDB → Cinemeta → fallback IMDB lookup | **KEEP** — needed for IMDB ID resolution |
| ~186-193 | Fallback IMDB lookup for movies | **KEEP** |

---

## scraper/services/comet.py

### `_scrape(instance, query, altquery)` — Lines 101-409

Same pattern as aiostreams. Has similar verbose per-stream debug logs.

##### Debug Logging (candidates for removal)

| Line | Message | Verdict |
|------|---------|---------|
| ~104 | `[instance.name] debug: scrape called...` | **REMOVE** |
| ~116 | `[instance.name] debug: B64Config loaded...` | **REMOVE** |
| ~122 | `[instance.name] debug: X not in active...` | **KEEP** |
| ~132 | `[instance.name] debug: X is active...` | **REMOVE** |
| ~206 | `[instance.name] debug: querying movie API...` | **REMOVE** |
| ~293 | `[instance.name] debug: found X streams` | **KEEP** |
| ~307 | `[instance.name] warning: ...` | **KEEP** |
| ~341 | `[instance.name] debug: stream X has no info hash...` | **REMOVE** |

---

## frontend.py & frontend_jobs.py

### frontend.py

- **Cleanup:** Mostly clean. Error handling is appropriate for HTTP API endpoints.
- **Debug logging:** `_log_frontend()` calls are minimal and useful. Keep.

### frontend_jobs.py

- **Cleanup:** Clean. `JobRegistry` is well-structured.
- `serialize_release()` / `serialize_releases()` — Keep as-is (browser safety layer).

---

## Other Modules

### base/__init__.py
- `custom_session` has built-in 429/503 rate-limiting with automatic retry. **KEEP**.
- Language/country mapping tables. **KEEP**.

### store/__init__.py
- `load()` / `save()` with pickle. Clean. **KEEP**.

### settings/__init__.py
- Descriptor-based config system. Clean. **KEEP**.

### ui/ui_print.py
- Centralized logging. **KEEP**.

### releases/__init__.py
- Release model + sort/scoring system. **KEEP**.

---

## Cleanup Priority Matrix

### Priority 1 — Remove Immediately (Debug Noise)

These are verbose per-item debug logs that produce dozens of lines per scrape with no operational value:

| File | What to Remove | Impact |
|------|---------------|--------|
| `realdebrid.py` ~206 | Per-release `debug: checking release:` with type/download preview | Eliminates ~100+ lines per scrape |
| `realdebrid.py` ~225-230 | `http download url:` and `http release ready for download:` | Removes redundant URL logging |
| `realdebrid.py` ~248, ~810 | `debug: checking if download_id is in downloading list` | Removes internal state dumps |
| `realdebrid.py` ~530 | `debug: got link for video file:` per-file | Removes per-file noise |
| `realdebrid.py` ~590-595 | `debug: filenames from RD unrestrict:` + `debug: download links:` | Removes raw data dumps |
| `realdebrid.py` ~815 | `warning: download_id not found in downloading list` | Development-only check |
| `downloader/__init__.py` ~133 | `Response snippet (first 2KB):` for 0-byte downloads | Removes binary dump |
| `downloader/__init__.py` ~153 | `Small response snippet (first 2KB):` for small files | Removes binary dump |
| `downloader/__init__.py` ~550 | `Processing element type:` | Routine diagnostic |
| `aiostreams.py` | All per-stream `debug:` lines (~247, ~337, ~359, ~397, ~420) | Eliminates ~500+ lines per scrape |
| `comet.py` | All per-stream `debug:` lines (~341 etc.) | Same |

### Priority 2 — Remove Failover Code (Now Redundant)

| File | What to Remove | Why It Was Added | Why It's Safe to Remove |
|------|---------------|-----------------|------------------------|
| `realdebrid.py` ~310-380 | HTTP URL fallback in magnet path (cached) | Scrapers didn't set `type="http"` | Scrapers now set it correctly |
| `realdebrid.py` ~760-790 | HTTP URL fallback in magnet path (uncached) | Same reason | Same |
| `realdebrid.py` ~177-187 | Double HTTP detection (type attr + URL prefix) | Belt-and-suspenders | Can simplify to just check `release.type == "http"` |
| `downloader/__init__.py` ~147-200 | Ranged retry for small files (<5MB) | CDN returned truncated responses | Downloads work correctly now |

### Priority 3 — Remove Entire Code Paths (If Cached-Only)

If you only use cached downloads from RD:

| File | What to Remove | Lines | Impact |
|------|---------------|-------|--------|
| `realdebrid.py` | Entire uncached download branch | ~730-850+ | Removes ~120 lines of duplicate code |
| `realdebrid.py` | Uncached torrent keepalive logic | ~660-670 | Removes uncached state tracking |
| `realdebrid.py` ~609 | `time.sleep(0.1)` before uncached selectFiles | Single line | Trivial |

### Priority 4 — Refactor (Code Deduplication)

| Pattern | Current Copies | Suggested Fix |
|---------|---------------|---------------|
| Jellyfin + Seerr refresh after download | 4 places in realdebrid.py | Extract to `_post_download_refresh(element)` helper |
| db.downloading removal | 3 places in realdebrid.py | Extract to `_remove_from_downloading(element)` helper |
| HTTP URL detection in magnet path | 2 places (cached + uncached) | Remove entirely (Priority 2) or extract to helper |

### Priority 5 — Diagnostic Functions (Optional Remove)

| File | Function | Purpose | Verdict |
|------|----------|---------|---------|
| `realdebrid.py` | `account_info()` | Fetch RD user info | Remove if never called in production |
| `realdebrid.py` | `torrents_list(limit=50)` | List RD torrents | Remove if never called in production |
