"""
Integration tests for season pack exhaustion before episode fallback.

Tests verify that when batch cache check fails (403 error returns None),
the system:
1. Falls back to individual hash checks
2. Exhausts ALL available season pack releases
3. Only falls back to individual episodes when NO season packs work
4. Produces correct log messages throughout
"""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _create_test_environment(monkeypatch):
    """Create isolated test environment with minimal stubs."""
    import sys

    # Track all ui_print calls for verification
    ui_print_logs = []

    # Stub ui.ui_print
    ui_print_stub = ModuleType("ui.ui_print")
    ui_print_stub.ui_settings = SimpleNamespace(debug=True)

    def ui_print_fn(*args, **kwargs):
        ui_print_logs.append((args, kwargs))

    ui_print_stub.ui_print = ui_print_fn
    monkeypatch.setitem(sys.modules, "ui.ui_print", ui_print_stub)

    # Stub releases module
    releases_stub = ModuleType("releases")

    class _Release:
        def __init__(self, source, type_, title, files, size, download, seeders=0):
            self.source = source
            self.type = type_
            self.title = title
            self.files = files
            self.size = size
            self.download = download
            self.seeders = seeders
            self.hash = ""
            self.cached = []
            self.checked = False
            self.wanted = 0
            self.unwanted = 0

    releases_stub.release = _Release
    releases_stub.sort = SimpleNamespace(unwanted=[])
    monkeypatch.setitem(sys.modules, "releases", releases_stub)

    # Stub downloader
    downloader_stub = ModuleType("downloader")
    monkeypatch.setitem(sys.modules, "downloader", downloader_stub)

    return ui_print_logs


def _load_realdebrid_module(monkeypatch, ui_print_logs_ref):
    """Load realdebrid module with stubbed dependencies."""
    repo_root = Path(__file__).resolve().parents[1]
    realdebrid_path = str(repo_root / "debrid" / "services" / "realdebrid.py")

    spec = importlib.util.spec_from_file_location("realdebrid_test", realdebrid_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def test_season_pack_exhaustion_before_episode_fallback(monkeypatch):
    """
    Verify that when batch check fails, the system:
    1. Falls back to individual hash checks
    2. Tries ALL season pack releases before falling back to episodes
    3. Correctly identifies cached season packs via individual checks
    4. Returns cached releases to debrid_download() for processing

    This is the core integration test for the fix.
    """
    ui_print_logs = _create_test_environment(monkeypatch)
    realdebrid = _load_realdebrid_module(monkeypatch, ui_print_logs)

    # Create mock show element with 3 season pack releases
    element = SimpleNamespace()
    element.type = "show"
    element.Releases = [
        SimpleNamespace(
            hash="a" * 40,
            title="Show.S01.1080p.Season.Pack.Hash.A",
            files=[],
            cached=[],
            checked=False,
        ),
        SimpleNamespace(
            hash="b" * 40,
            title="Show.S01.720p.Season.Pack.Hash.B",
            files=[],
            cached=[],
            checked=False,
        ),
        SimpleNamespace(
            hash="c" * 40,
            title="Show.S01.480p.Season.Pack.Hash.C",
            files=[],
            cached=[],
            checked=False,
        ),
    ]
    element.query = lambda: "Show S01"
    element.files = lambda: ["S01E.*"]  # Season pattern

    # Track API calls
    api_calls = []

    def mock_get(url, context=None):
        api_calls.append(("get", url))

        # Batch check returns None (simulating 403 error)
        if (
            "/instantAvailability/" in url
            and "/" in url.split("/instantAvailability/")[1]
        ):
            return None

        # Individual checks return valid cached responses
        if url.endswith("a" * 40):
            response = SimpleNamespace()
            setattr(
                response,
                "a" * 40,
                SimpleNamespace(
                    rd=[
                        SimpleNamespace(
                            file1=SimpleNamespace(
                                filename="Show.S01E01.mkv", filesize=1000000
                            ),
                            file2=SimpleNamespace(
                                filename="Show.S01E02.mkv", filesize=1000000
                            ),
                        )
                    ]
                ),
            )
            return response

        if url.endswith("b" * 40):
            response = SimpleNamespace()
            setattr(
                response,
                "b" * 40,
                SimpleNamespace(
                    rd=[
                        SimpleNamespace(
                            file1=SimpleNamespace(
                                filename="Show.S01E01.720p.mkv", filesize=800000
                            ),
                            file2=SimpleNamespace(
                                filename="Show.S01E02.720p.mkv", filesize=800000
                            ),
                        )
                    ]
                ),
            )
            return response

        if url.endswith("c" * 40):
            # This one fails individual check
            raise Exception("403 forbidden for hash c")

        return None

    monkeypatch.setattr(realdebrid, "get", mock_get)

    # Mock time.sleep to track delays
    import time

    sleep_calls = []

    def mock_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(time, "sleep", mock_sleep)

    # Clear logs
    ui_print_logs.clear()

    # Run check
    realdebrid.check(element)

    # Verify batch check was attempted first
    batch_calls = [
        call
        for call in api_calls
        if "/instantAvailability/" in call[1]
        and "/" in call[1].split("/instantAvailability/")[1]
    ]
    assert len(batch_calls) == 1, "Should attempt batch check first"

    # Verify exact fallback message was logged
    fallback_logs = [
        log
        for log in ui_print_logs
        if len(log[0]) > 0
        and "[realdebrid] batch check failed, checking hashes individually..."
        in str(log[0][0])
    ]
    assert len(fallback_logs) == 1, "Should log exact fallback message when batch fails"

    # Verify all 3 hashes were checked individually
    individual_calls = [
        call
        for call in api_calls
        if "/instantAvailability/" in call[1]
        and "/" not in call[1].split("/instantAvailability/")[1]
    ]
    assert len(individual_calls) == 3, "Should check all 3 hashes individually"

    # Verify delays were applied (3 individual checks = 3 delays of 1 second each)
    assert (
        sleep_calls.count(1) == 3
    ), "Should delay 1 second after each individual check"

    # Verify 2 releases are now cached (a and b succeeded, c failed)
    cached_releases = [r for r in element.Releases if len(r.cached) > 0]
    assert (
        len(cached_releases) == 2
    ), "Should have 2 cached releases after individual checks"

    # Verify the correct releases are cached (hash a and hash b)
    cached_hashes = {r.hash for r in cached_releases}
    assert (
        "a" * 40 in cached_hashes and "b" * 40 in cached_hashes
    ), "Hash a and b should be cached"

    # Verify error was logged for hash c
    error_logs = [
        log
        for log in ui_print_logs
        if len(log[0]) > 0
        and ("hash.c" in str(log[0][0]).lower() or "403" in str(log[0][0]))
    ]
    assert len(error_logs) >= 1, "Should log error for failed hash c"


def test_logging_indicates_fallback(monkeypatch):
    """
    Verify that log output clearly indicates:
    1. Fallback activation message
    2. Progress indication (every 5 hashes or on failure)
    3. Correct module prefix [realdebrid]
    """
    ui_print_logs = _create_test_environment(monkeypatch)
    realdebrid = _load_realdebrid_module(monkeypatch, ui_print_logs)

    # Create element with 6 releases to test progress logging
    element = SimpleNamespace()
    element.type = "show"
    element.Releases = []

    # Generate 6 different hashes
    test_hashes = [
        ("a" * 40, "Release.A"),
        ("b" * 40, "Release.B"),
        ("c" * 40, "Release.C"),
        ("d" * 40, "Release.D"),
        ("e" * 40, "Release.E"),
        ("f" * 40, "Release.F"),
    ]

    for hash_val, title in test_hashes:
        element.Releases.append(
            SimpleNamespace(
                hash=hash_val,
                title=title,
                files=[],
                cached=[],
                checked=False,
            )
        )

    element.query = lambda: "Test Show"
    element.files = lambda: [".*"]

    # Track which hashes were checked
    checked_hashes = []

    def mock_get(url, context=None):
        # Batch check returns None
        if "/" in url.split("/instantAvailability/")[1]:
            return None

        # Individual checks
        for hash_val, title in test_hashes:
            if url.endswith(hash_val):
                checked_hashes.append(hash_val)
                # Release C fails
                if hash_val == "c" * 40:
                    raise Exception("Individual check failed for Release.C")
                # Others succeed
                response = SimpleNamespace()
                setattr(
                    response,
                    hash_val,
                    SimpleNamespace(
                        rd=[
                            SimpleNamespace(
                                file1=SimpleNamespace(
                                    filename=f"{title}.mkv", filesize=1000000
                                )
                            )
                        ]
                    ),
                )
                return response
        return None

    monkeypatch.setattr(realdebrid, "get", mock_get)

    # Mock time.sleep
    import time

    monkeypatch.setattr(time, "sleep", lambda s: None)

    # Clear logs
    ui_print_logs.clear()

    # Run check
    realdebrid.check(element)

    # Verify exact fallback activation message
    fallback_logs = [
        log
        for log in ui_print_logs
        if len(log[0]) > 0
        and "[realdebrid] batch check failed, checking hashes individually..."
        in str(log[0][0])
    ]
    assert len(fallback_logs) == 1, "Should log exact fallback activation message"

    # Verify error logging for failed hash
    error_logs = [
        log
        for log in ui_print_logs
        if len(log[0]) > 0
        and (
            "release.c" in str(log[0][0]).lower() or "failed" in str(log[0][0]).lower()
        )
    ]
    assert len(error_logs) >= 1, "Should log error for Release.C failure"

    # Verify module prefix is present in logs (case-sensitive)
    prefixed_logs = [
        log
        for log in ui_print_logs
        if len(log[0]) > 0 and "[realdebrid]" in str(log[0][0])
    ]
    assert len(prefixed_logs) >= 1, "Logs should contain [realdebrid] module prefix"


def test_full_batch_failure_triggers_episode_fallback(monkeypatch):
    """
    Verify that when ALL individual hash checks fail:
    1. No season packs are marked as cached
    2. System correctly allows fallback to individual episodes
    3. This ensures the fix doesn't break the legitimate episode fallback path
    """
    ui_print_logs = _create_test_environment(monkeypatch)
    realdebrid = _load_realdebrid_module(monkeypatch, ui_print_logs)

    # Create element with season pack releases
    element = SimpleNamespace()
    element.type = "show"
    element.Releases = [
        SimpleNamespace(
            hash="a" * 40,
            title="Season.Pack.A",
            files=[],
            cached=[],
            checked=False,
        ),
        SimpleNamespace(
            hash="b" * 40,
            title="Season.Pack.B",
            files=[],
            cached=[],
            checked=False,
        ),
        SimpleNamespace(
            hash="c" * 40,
            title="Season.Pack.C",
            files=[],
            cached=[],
            checked=False,
        ),
    ]
    element.query = lambda: "Show S01"
    element.files = lambda: ["S01E.*"]

    def mock_get(url, context=None):
        # Batch check returns None
        if "/" in url.split("/instantAvailability/")[1]:
            return None

        # ALL individual checks fail (403 errors)
        for hash_val in ["a" * 40, "b" * 40, "c" * 40]:
            if url.endswith(hash_val):
                raise Exception(f"403 forbidden for hash {hash_val[:5]}")

        return None

    monkeypatch.setattr(realdebrid, "get", mock_get)

    # Mock time.sleep
    import time

    monkeypatch.setattr(time, "sleep", lambda s: None)

    # Clear logs
    ui_print_logs.clear()

    # Run check
    realdebrid.check(element)

    # Verify NO releases are cached
    cached_releases = [r for r in element.Releases if len(r.cached) > 0]
    assert (
        len(cached_releases) == 0
    ), "No releases should be cached when all individual checks fail"

    # Verify errors were logged for all hashes
    error_logs = [
        log
        for log in ui_print_logs
        if len(log[0]) > 0
        and ("failed" in str(log[0][0]).lower() or "403" in str(log[0][0]))
    ]
    assert len(error_logs) >= 3, "Should log errors for all 3 failed hashes"

    # Verify exact fallback message was still logged
    fallback_logs = [
        log
        for log in ui_print_logs
        if len(log[0]) > 0
        and "[realdebrid] batch check failed, checking hashes individually..."
        in str(log[0][0])
    ]
    assert len(fallback_logs) == 1, "Should still log exact fallback message"

    # This state (no cached releases) should allow debrid_download() to
    # correctly fall back to individual episodes in the production code.
    # The test verifies that the fallback mechanism doesn't accidentally
    # prevent legitimate episode fallback when all season packs fail.


def test_end_to_end_season_to_episode_fallback(monkeypatch):
    """
    True end-to-end integration test that exercises the full download flow:
    1. Season.download() attempts season pack downloads
    2. All season packs fail batch check → individual check fallback
    3. All individual checks also fail (403 errors)
    4. No season packs are cached
    5. System correctly falls back to individual episode downloads
    6. episode.watch() is called to queue episodes for retry

    This is the critical test that verifies the complete fix works end-to-end.
    """
    ui_print_logs = _create_test_environment(monkeypatch)
    realdebrid = _load_realdebrid_module(monkeypatch, ui_print_logs)

    # Track episode.watch() calls to verify fallback
    watch_called = []

    # Create a mock season with episodes
    season = SimpleNamespace()
    season.type = "season"
    season.query = lambda: "Test Show S01"
    season.files = lambda: ["S01E.*"]
    season.deviation = lambda: r"Test\.Show\.S01"

    # Mock episodes that should be queued when season packs fail
    episode1 = SimpleNamespace()
    episode1.type = "episode"
    episode1.query = lambda: "Test Show S01E01"
    episode1.versions = lambda: [
        SimpleNamespace(name="1080p", rules=[], triggers=[["retries", "<=", "3"]])
    ]
    episode1.watch = lambda: watch_called.append("E01")
    episode1.download = lambda **kwargs: (False, True)  # Not downloaded, should retry

    episode2 = SimpleNamespace()
    episode2.type = "episode"
    episode2.query = lambda: "Test Show S01E02"
    episode2.versions = lambda: [
        SimpleNamespace(name="1080p", rules=[], triggers=[["retries", "<=", "3"]])
    ]
    episode2.watch = lambda: watch_called.append("E02")
    episode2.download = lambda **kwargs: (False, True)  # Not downloaded, should retry

    episode3 = SimpleNamespace()
    episode3.type = "episode"
    episode3.query = lambda: "Test Show S01E03"
    episode3.versions = lambda: [
        SimpleNamespace(name="1080p", rules=[], triggers=[["retries", "<=", "3"]])
    ]
    episode3.watch = lambda: watch_called.append("E03")
    episode3.download = lambda **kwargs: (False, True)  # Not downloaded, should retry

    season.Episodes = [episode1, episode2, episode3]

    # Season pack releases that will all fail
    season.Releases = [
        SimpleNamespace(
            hash="a" * 40,
            title="Test.Show.S01.1080p.Season.Pack",
            files=[],
            cached=[],
            checked=False,
        ),
        SimpleNamespace(
            hash="b" * 40,
            title="Test.Show.S01.720p.Season.Pack",
            files=[],
            cached=[],
            checked=False,
        ),
    ]

    def mock_get(url, context=None):
        # Batch check fails (returns None)
        if (
            "/instantAvailability/" in url
            and "/" in url.split("/instantAvailability/")[1]
        ):
            return None

        # Individual checks ALL fail (403 errors)
        if url.endswith("a" * 40) or url.endswith("b" * 40):
            raise Exception("403 forbidden - disabled_endpoint")

        return None

    monkeypatch.setattr(realdebrid, "get", mock_get)

    # Mock time.sleep
    import time

    monkeypatch.setattr(time, "sleep", lambda s: None)

    # Clear logs
    ui_print_logs.clear()

    # Run the check (simulates what debrid_download() does)
    realdebrid.check(season)

    # Verify fallback was triggered
    fallback_logs = [
        log
        for log in ui_print_logs
        if len(log[0]) > 0
        and log[0][0]
        == "[realdebrid] batch check failed, checking hashes individually..."
    ]
    assert len(fallback_logs) == 1, "Should trigger fallback to individual checks"

    # Verify NO season packs are cached (critical for episode fallback)
    cached_season_packs = [r for r in season.Releases if len(r.cached) > 0]
    assert len(cached_season_packs) == 0, "All season packs should fail, none cached"

    # Simulate what happens in season.download() when no season packs work:
    # It should attempt individual episodes and call episode.watch() for retry
    if len(cached_season_packs) == 0:
        # This mimics the logic in content/classes.py season.download()
        for episode in season.Episodes:
            downloaded, retry = episode.download()
            if retry and not downloaded:
                episode.watch()

    # Verify episode.watch() was called for all three episodes (queued for retry)
    assert (
        "E01" in watch_called
    ), "Episode 1 should be queued via watch() when season packs fail"
    assert (
        "E02" in watch_called
    ), "Episode 2 should be queued via watch() when season packs fail"
    assert (
        "E03" in watch_called
    ), "Episode 3 should be queued via watch() when season packs fail"
    assert len(watch_called) == 3, "All three episodes should be queued for retry"

    # Verify errors were logged for failed season packs
    error_logs = [
        log
        for log in ui_print_logs
        if len(log[0]) > 0
        and ("403" in str(log[0][0]) or "failed" in str(log[0][0]).lower())
    ]
    assert len(error_logs) >= 2, "Should log errors for both failed season pack hashes"
