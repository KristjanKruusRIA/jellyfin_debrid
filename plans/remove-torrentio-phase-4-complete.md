## Phase 4 Complete: Stale-config migration and guardrails

Added runtime filtering and warning logic so users with stale `"torrentio"` entries in their Sources config receive clear feedback instead of silently having zero scraper results. The approach warns about unsupported sources via `ui_print()` and continues with any remaining valid sources.

**Files created/changed:**
- scraper/services/__init__.py
- tests/test_scraper_source_migration.py
- tests/test_scraper_services_registration.py

**Functions created/changed:**
- `_supported_services_map()` — new helper to build name→module map from registered scrapers
- `_supported_sources_text()` — new helper to format supported source names for messages
- `_warn_unsupported_source()` — new helper to log per-source warning
- `_error_no_supported_sources()` — new helper to log empty-sources error
- `get()` — refactored to filter unsupported sources with warnings
- `sequential()` — refactored to filter unsupported sources with warnings

**Tests created/changed:**
- `test_get_warns_on_unsupported_source`
- `test_get_errors_on_all_unsupported`
- `test_get_works_with_valid_sources_only`
- `test_sequential_warns_on_unsupported_source`

**Review Status:** APPROVED

**Git Commit Message:**
```
feat: add stale-config migration for removed scrapers

- Filter unsupported source names in get() and sequential()
- Warn users about ignored sources like 'torrentio' in config
- Emit clear error when all configured sources are unsupported
- Add 4 tests for source migration guardrail scenarios
```
