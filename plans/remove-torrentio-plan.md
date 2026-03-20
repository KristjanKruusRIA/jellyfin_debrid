# Plan: Remove Torrentio from jellyfin_debrid

**Created:** 2026-03-20
**Status:** Ready for Atlas Execution

## Summary

Remove Torrentio as a supported scraper from the application code, settings registry, defaults, and user-facing documentation while keeping the app fully functional with the remaining `aiostreams` and `comet` scrapers. The highest-risk part of this change is not deleting `scraper/services/torrentio.py` itself, but eliminating hard imports and Torrentio-specific runtime assumptions that currently exist in scraper registration, settings wiring, and scrape heuristics. The implementation should include a compatibility/migration path for existing configs that still contain `"torrentio"` in `Sources`, because otherwise the app can quietly scrape nothing while still passing preflight.

## Context & Analysis

**Relevant Files:**
- `scraper/services/__init__.py`: Hard-imports `torrentio`, seeds `scrapers = [torrentio]`, and sets `active_default = ["torrentio"]`; must be refactored first to avoid startup breakage.
- `settings/__init__.py`: Defines hidden `Torrentio Scraper Parameters` and references `_lazy_scraper_services.torrentio`; must be cleaned to prevent settings import failures.
- `content/classes.py`: Contains Torrentio-specific comments and movie-scrape logic that imports `scraper.services.torrentio` to read its `limit=...` configuration.
- `scraper/__init__.py`: Aggregates active scrapers; stale source names can be silently ignored here, which creates a migration risk for old configs.
- `ui/__init__.py`: Settings/preflight flow currently validates that `Sources` is non-empty, not that source names resolve to real scraper modules.
- `content/services/jellyseerr.py`: Still documents IMDB prioritization as Torrentio-specific even though remaining scrapers can also benefit from IMDB IDs.
- `settings.json.template`: Still includes `"torrentio"` in `Sources` and the `Torrentio Scraper Parameters` key.
- `README.md`: Still advertises Torrentio as a supported scraper and shows it in the sample config.
- `config/settings.json`: Current local config already uses only `aiostreams` and `comet`, which is a good signal that the runtime can work without Torrentio once code/default wiring is cleaned.
- `scraper/services/torrentio.py`: Service implementation to remove or retire after all wiring is updated.
- `.github/copilot-instructions.md`: Internal contributor guidance still names Torrentio as an active scraper; optional but worthwhile cleanup.

**Key Functions/Classes:**
- `scraper.services.__subclasses__()`, `get()`, `sequential()` in `scraper/services/__init__.py`: determine the registered/active scraper set.
- `scraper.scrape()` in `scraper/__init__.py`: orchestrates scraping and will silently proceed with an empty sequence if source names no longer resolve.
- `content.classes.media.download()` / season/movie scrape branches in `content/classes.py`: contain the Torrentio-specific `overall_limit` import and IMDB-first rationale comments.
- `settings.setting(...)` entries in `settings/__init__.py`: control the visible/hidden scraper settings UI.
- Jellyseerr `movie`/`show` constructors in `content/services/jellyseerr.py`: still annotate IMDB insertion as being specifically for Torrentio.

**Dependencies:**
- `aiostreams` and `comet`: remaining scraper backends that will become the full supported scraper surface after Torrentio removal.
- `regex`: used in `content/classes.py` for scrape heuristics and in settings validation text.
- Current settings persistence model: stale keys/values in user config are possible and need explicit handling.

**Patterns & Conventions:**
- Scrapers are module-style services with `name`, `setup(cls, new=False)`, and `scrape(query, altquery)`.
- Scraper registration is centralized in `scraper/services/__init__.py`.
- Settings are declared centrally in `settings/__init__.py`, including hidden per-scraper settings.
- Logging/output should continue to use `ui_print()` for user-visible warnings or migration notices.
- The codebase currently favors resilience by ignoring unavailable services where practical; the removal should follow that pattern, but with better stale-config handling so the failure mode is visible instead of silent.

## Implementation Phases

### Phase 1: Remove Torrentio from startup wiring

**Objective:** Eliminate all hard imports and default registrations so the app can start cleanly without Torrentio present.

**Files to Modify/Create:**
- `scraper/services/__init__.py`: remove Torrentio import, rebuild `scrapers`/`active_default` from remaining supported modules.
- `scraper/services/torrentio.py`: either delete the module or replace it with a short compatibility stub only if needed during an intermediate step.

**Tests to Write:**
- `tests/test_scraper_services_registration.py`: verifies that `scraper.services.get()` and `active_default` only expose `aiostreams` and `comet` after removal.
- `tests/test_scraper_services_registration.py`: verifies importing `scraper.services` does not require Torrentio.

**Steps:**
1. Write a test that imports `scraper.services` and asserts Torrentio is not in the registered/default scraper list.
2. Run the test and confirm it fails against current wiring.
3. Refactor `scraper/services/__init__.py` to remove the Torrentio import and default registration.
4. Remove or retire `scraper/services/torrentio.py` only after import paths are clean.
5. Re-run targeted tests and lint/format the touched files.

**Acceptance Criteria:**
- [ ] Importing `scraper.services` succeeds without Torrentio.
- [ ] `active_default` contains only supported scrapers.
- [ ] No code path still hard-imports `scraper.services.torrentio` during startup.
- [ ] All phase tests pass.

---

### Phase 2: Remove Torrentio-specific settings and defaults

**Objective:** Clean the settings registry and default config so new installs no longer expose or persist Torrentio-specific configuration.

**Files to Modify/Create:**
- `settings/__init__.py`: remove the hidden `Torrentio Scraper Parameters` setting and any direct service references.
- `settings.json.template`: remove `"torrentio"` from default `Sources` and delete the `Torrentio Scraper Parameters` entry.
- `README.md`: update supported scrapers and example config.
- Optional: `.github/copilot-instructions.md`: update internal docs to reflect the new supported scraper set.

**Tests to Write:**
- `tests/test_settings_scrapers.py`: verifies the scraper settings registry does not expose a Torrentio setting.
- `tests/test_settings_scrapers.py`: verifies the template/default sources list excludes Torrentio.

**Steps:**
1. Add tests that exercise the settings registry and the sample template expectations.
2. Run the tests and confirm current settings/docs still reference Torrentio.
3. Remove the Torrentio-specific settings entry and update default `Sources` to the remaining scrapers.
4. Update docs/examples to mention only supported scrapers.
5. Re-run targeted tests and lint/format the touched files.

**Acceptance Criteria:**
- [ ] No settings registry entry references Torrentio.
- [ ] `settings.json.template` contains only supported sources.
- [ ] README examples/documentation match the actual supported scraper set.
- [ ] All phase tests pass.

---

### Phase 3: Refactor Torrentio-specific scrape heuristics

**Objective:** Remove runtime logic that depends on Torrentio’s manifest/options while preserving sane scrape behavior for movies, shows, and seasons.

**Files to Modify/Create:**
- `content/classes.py`: remove the import of `scraper.services.torrentio`, replace Torrentio-derived `overall_limit` logic with a generic constant or shared helper, and update comments.
- `content/services/jellyseerr.py`: revise stale comments that say IMDB IDs are inserted specifically because Torrentio needs them.
- Optional helper file if Atlas decides to centralize scraper-limit behavior rather than inline a constant.

**Tests to Write:**
- `tests/test_content_scrape_heuristics.py`: verifies movie scrape flow no longer imports Torrentio to compute scrape limits.
- `tests/test_content_scrape_heuristics.py`: verifies IMDB/TMDB fallback logic still works when only remaining scrapers are available.

**Steps:**
1. Add a test that exercises the movie scrape heuristic without a Torrentio module present.
2. Run the test and confirm the current logic still tries to import Torrentio.
3. Replace Torrentio-specific `overall_limit` behavior with an explicit, scraper-agnostic limit strategy.
4. Update stale comments to describe the remaining scraper ecosystem accurately.
5. Re-run targeted tests and lint/format the touched files.

**Acceptance Criteria:**
- [ ] `content/classes.py` contains no Torrentio import or Torrentio-specific heuristic dependency.
- [ ] Scrape fallback behavior remains deterministic and documented.
- [ ] IMDB/TMDB rationale comments are accurate after removal.
- [ ] All phase tests pass.

---

### Phase 4: Add stale-config migration and guardrails

**Objective:** Prevent existing users with `"torrentio"` still saved in `Sources` from ending up in a silent “no releases found” state.

**Files to Modify/Create:**
- `ui/__init__.py`: adjust preflight/load behavior or settings repair path.
- `scraper/services/__init__.py` and/or `settings/__init__.py`: add a normalization/filter step for unsupported source names if that is the chosen migration location.
- Potentially `scraper/__init__.py`: optionally surface a warning when resolved scraper sequences are empty.

**Tests to Write:**
- `tests/test_scraper_source_migration.py`: verifies stale `torrentio` entries are removed or warned on load.
- `tests/test_scraper_source_migration.py`: verifies a config containing only `torrentio` does not silently pass into an empty scrape set without user feedback.

**Steps:**
1. Decide the migration strategy: auto-remove unsupported sources, warn-and-rewrite config, or fail preflight with a clear message.
2. Write tests for the chosen behavior using a config fixture that still contains `torrentio`.
3. Implement normalization and user-visible warning behavior using `ui_print()`.
4. Ensure the app lands on a valid supported source set or blocks with actionable guidance.
5. Re-run targeted tests and lint/format the touched files.

**Acceptance Criteria:**
- [ ] Old configs containing `torrentio` are handled explicitly.
- [ ] Users are not left in a silent empty-scrape state.
- [ ] The app either repairs unsupported sources automatically or emits a clear actionable warning/error.
- [ ] All phase tests pass.

---

### Phase 5: Validate end-to-end supported-scraper behavior

**Objective:** Confirm the application still functions as expected with only `aiostreams` and `comet` enabled.

**Files to Modify/Create:**
- `tests/test_aiostreams.py`: update only if fixture assumptions depend on source registration/defaults.
- `tests/test_integration_season_packs.py`: verify no hidden Torrentio dependency leaks into season-pack behavior.
- `tests/test_realdebrid_fallback.py`: verify no hidden Torrentio dependency in RD fallback paths.
- Add a new integration-ish smoke test if needed for source resolution with `aiostreams` + `comet` only.

**Tests to Write:**
- `tests/test_supported_scrapers_only.py`: verifies supported-source resolution and scrape orchestration with just `aiostreams`/`comet`.
- Re-run existing scraper/debrid tests most likely to expose hidden assumptions.

**Steps:**
1. Add a smoke test for source resolution and orchestration with the supported scraper pair only.
2. Run targeted existing tests covering AIOStreams, season packs, and RealDebrid fallback.
3. Fix any hidden assumptions uncovered by the run.
4. Run the broader test suite appropriate for touched files.
5. Perform final lint/format verification.

**Acceptance Criteria:**
- [ ] The supported scraper pair works without Torrentio installed or configured.
- [ ] Existing AIOStreams/Comet/RealDebrid behavior remains intact.
- [ ] No hidden Torrentio assumptions remain in tested flows.
- [ ] All phase tests pass.

## Open Questions

1. Should Torrentio be fully deleted, or retained briefly as a compatibility stub?
   - **Option A:** Delete `scraper/services/torrentio.py` immediately.
     - **Tradeoff:** Cleaner end state, but any leftover import path fails hard during development if not removed everywhere first.
   - **Option B:** Replace it with a temporary compatibility stub that logs deprecation and returns no results.
     - **Tradeoff:** Safer rollout for partial cleanup, but extends dead code lifetime.
   - **Recommendation:** Delete it in the same change set as the import/settings cleanup unless Atlas discovers external packaging constraints.

2. How should stale `Sources` configs be handled?
   - **Option A:** Auto-filter unsupported sources and rewrite/save the cleaned config.
     - **Tradeoff:** Best UX, but modifies user config automatically.
   - **Option B:** Fail preflight with a clear message telling the user to reselect sources.
     - **Tradeoff:** More explicit, but more disruptive.
   - **Option C:** Warn but continue with any remaining supported sources.
     - **Tradeoff:** Minimal behavior change, but still risks confusion when no supported sources remain.
   - **Recommendation:** Auto-filter unsupported source names and emit a clear `ui_print()` warning; if nothing valid remains, fail preflight with actionable instructions.

3. What should replace the Torrentio-derived `limit=...` movie heuristic?
   - **Option A:** Use a fixed scraper-agnostic cap (for example, keep the existing fallback threshold semantics).
   - **Option B:** Add a shared helper/config for overall scrape attempt limits.
   - **Recommendation:** Start with a local scraper-agnostic helper/constant in `content/classes.py`; only extract a broader abstraction if the cleanup exposes repeated logic.

## Risks & Mitigation

- **Risk:** Partial cleanup leaves hard imports that crash startup.
  - **Mitigation:** Phase 1 must land before deleting the service file; add import-focused tests first.

- **Risk:** Old configs still containing `torrentio` quietly produce no releases.
  - **Mitigation:** Add explicit stale-source normalization/preflight behavior in Phase 4.

- **Risk:** Removing Torrentio changes scrape volume or ID fallback behavior unexpectedly.
  - **Mitigation:** Replace Torrentio-specific heuristics with explicit shared behavior and cover it with focused tests.

- **Risk:** Documentation and templates drift from actual functionality.
  - **Mitigation:** Update template, README, and optional internal docs in the same change set.

- **Risk:** Existing visible tests do not catch source-registration/settings regressions.
  - **Mitigation:** Add new focused tests for registration, settings, and stale-config migration.

## Success Criteria

- [ ] Torrentio is no longer registered, configured, documented, or required anywhere in runtime code.
- [ ] The app starts and operates with only `aiostreams` and `comet` as supported scrapers.
- [ ] Old configs referencing `torrentio` are handled explicitly and safely.
- [ ] Scrape heuristics no longer import or depend on Torrentio.
- [ ] All relevant tests pass.
- [ ] Docs and templates match the new supported feature set.

## Notes for Atlas

- No `AGENTS.md` was present, so this plan is written to the default `plans/` directory.
- The local `config/settings.json` already uses only `aiostreams` and `comet`, which suggests the desired end state is operationally viable; don’t rely on that file as product truth, but do use it as a sanity check.
- Prioritize the stale-config user experience. The biggest non-obvious regression here is a haunted setup where `Sources` is non-empty but resolves to zero real scraper modules.
- Keep edits surgical and avoid unrelated scraper/debrid changes. This task is about removing Torrentio cleanly, not redesigning the scraper architecture in one heroic sweep.
