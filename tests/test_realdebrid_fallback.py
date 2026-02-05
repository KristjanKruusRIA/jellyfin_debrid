"""
Tests for RealDebrid batch check fallback to individual hash checks.

When batch checking fails (returns None due to 403 or other errors),
the system should gracefully degrade to checking hashes individually.
"""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock


def _load_realdebrid_module(monkeypatch):
    """Load realdebrid module directly to avoid package import side-effects."""
    repo_root = Path(__file__).resolve().parents[1]
    realdebrid_path = str(repo_root / "debrid" / "services" / "realdebrid.py")

    # Inject minimal stubs to avoid importing large package graph
    import sys

    # Stub ui.ui_print
    ui_print_stub = ModuleType("ui.ui_print")
    ui_print_stub.ui_settings = SimpleNamespace(debug=True)
    ui_print_logs = []

    def ui_print_fn(*a, **k):
        ui_print_logs.append((a, k))

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
    releases_stub.sort = SimpleNamespace(unwanted=[])  # Add sort.unwanted stub
    monkeypatch.setitem(sys.modules, "releases", releases_stub)

    # Stub downloader
    downloader_stub = ModuleType("downloader")
    monkeypatch.setitem(sys.modules, "downloader", downloader_stub)

    spec = importlib.util.spec_from_file_location("realdebrid_test", realdebrid_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module, ui_print_logs


def test_batch_check_success_path(monkeypatch):
    """Verify batch path unchanged when successful - no fallback triggered."""
    realdebrid, ui_print_logs = _load_realdebrid_module(monkeypatch)

    # Create mock element with releases
    element = SimpleNamespace()
    element.Releases = [
        SimpleNamespace(hash="a" * 40, title="Release 1", files=[], cached=[]),
        SimpleNamespace(hash="b" * 40, title="Release 2", files=[], cached=[]),
    ]
    element.query = lambda: "test context"
    element.files = lambda: [".*"]  # Return wanted files pattern

    # Mock successful batch response
    batch_response = SimpleNamespace()
    setattr(
        batch_response,
        "a" * 40,
        SimpleNamespace(
            rd=[
                SimpleNamespace(
                    file1=SimpleNamespace(filename="test.mkv", filesize=1000)
                )
            ]
        ),
    )
    setattr(
        batch_response,
        "b" * 40,
        SimpleNamespace(
            rd=[
                SimpleNamespace(
                    file1=SimpleNamespace(filename="test2.mkv", filesize=2000)
                )
            ]
        ),
    )

    # Mock the get function to return successful response
    mock_get = MagicMock(return_value=batch_response)
    monkeypatch.setattr(realdebrid, "get", mock_get)

    # Clear logs before check
    ui_print_logs.clear()

    # Run check
    realdebrid.check(element)

    # Verify batch endpoint was called once
    assert mock_get.call_count == 1
    batch_url = mock_get.call_args[0][0]
    assert "instantAvailability" in batch_url
    assert "/" + "a" * 40 + "/" + "b" * 40 in batch_url

    # Verify no fallback message
    fallback_logs = [
        log for log in ui_print_logs if "checking hashes individually" in str(log[0])
    ]
    assert len(fallback_logs) == 0, "Should not trigger fallback on successful batch"


def test_batch_check_403_triggers_fallback(monkeypatch):
    """Verify fallback triggered on None response from batch check."""
    realdebrid, ui_print_logs = _load_realdebrid_module(monkeypatch)

    # Create mock element with releases
    element = SimpleNamespace()
    element.Releases = [
        SimpleNamespace(hash="a" * 40, title="Release 1", files=[], cached=[]),
        SimpleNamespace(hash="b" * 40, title="Release 2", files=[], cached=[]),
    ]
    element.query = lambda: "test context"
    element.files = lambda: [".*"]  # Return wanted files pattern

    # Track get calls
    get_calls = []

    def mock_get(url, context=None):
        get_calls.append(url)
        # Return None for batch (simulating 403 error)
        if "/" + "a" * 40 + "/" + "b" * 40 in url:
            return None
        # Return valid response for individual checks
        if "a" * 40 in url:
            response = SimpleNamespace()
            setattr(
                response,
                "a" * 40,
                SimpleNamespace(
                    rd=[
                        SimpleNamespace(
                            file1=SimpleNamespace(filename="test.mkv", filesize=1000)
                        )
                    ]
                ),
            )
            return response
        if "b" * 40 in url:
            response = SimpleNamespace()
            setattr(
                response,
                "b" * 40,
                SimpleNamespace(
                    rd=[
                        SimpleNamespace(
                            file1=SimpleNamespace(filename="test2.mkv", filesize=2000)
                        )
                    ]
                ),
            )
            return response
        return None

    monkeypatch.setattr(realdebrid, "get", mock_get)

    # Mock time.sleep to track delay calls
    import time

    sleep_calls = []

    def mock_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(time, "sleep", mock_sleep)

    # Clear logs before check
    ui_print_logs.clear()

    # Run check
    realdebrid.check(element)

    # Verify batch endpoint was called first
    assert len(get_calls) >= 1
    assert "a" * 40 + "/" + "b" * 40 in get_calls[0]

    # Verify fallback message was logged
    fallback_logs = [
        log for log in ui_print_logs if "checking hashes individually" in str(log[0])
    ]
    assert len(fallback_logs) == 1, "Should log fallback message when batch fails"

    # Verify individual checks were made
    individual_calls = [
        url for url in get_calls if "/" not in url.split("instantAvailability/")[1]
    ]
    assert len(individual_calls) == 2, "Should check both hashes individually"

    # Verify 1-second delay was called twice (after each individual check)
    assert (
        sleep_calls.count(1) == 2
    ), "Should delay 1 second after each individual check"


def test_individual_checks_isolate_failures(monkeypatch):
    """Verify one bad hash doesn't affect others during individual fallback."""
    realdebrid, ui_print_logs = _load_realdebrid_module(monkeypatch)

    # Create mock element with 3 releases
    element = SimpleNamespace()
    element.Releases = [
        SimpleNamespace(hash="a" * 40, title="Release Good 1", files=[], cached=[]),
        SimpleNamespace(hash="b" * 40, title="Release Bad", files=[], cached=[]),
        SimpleNamespace(hash="c" * 40, title="Release Good 2", files=[], cached=[]),
    ]
    element.query = lambda: "test context"
    element.files = lambda: [".*"]  # Return wanted files pattern

    def mock_get(url, context=None):
        # Return None for batch
        if "/" + "a" * 40 in url and "/" + "b" * 40 in url:
            return None
        # Individual checks
        if url.endswith("a" * 40):
            response = SimpleNamespace()
            setattr(
                response,
                "a" * 40,
                SimpleNamespace(
                    rd=[
                        SimpleNamespace(
                            file1=SimpleNamespace(filename="test1.mkv", filesize=1000)
                        )
                    ]
                ),
            )
            return response
        if url.endswith("b" * 40):
            # Simulate failure for this hash
            raise Exception("Individual check failed for hash b")
        if url.endswith("c" * 40):
            response = SimpleNamespace()
            setattr(
                response,
                "c" * 40,
                SimpleNamespace(
                    rd=[
                        SimpleNamespace(
                            file1=SimpleNamespace(filename="test3.mkv", filesize=3000)
                        )
                    ]
                ),
            )
            return response
        return None

    monkeypatch.setattr(realdebrid, "get", mock_get)

    # Mock time.sleep to track delay calls
    import time

    sleep_calls = []

    def mock_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(time, "sleep", mock_sleep)

    # Clear logs before check
    ui_print_logs.clear()

    # Run check (should not crash)
    realdebrid.check(element)

    # Verify error was logged for bad hash
    error_logs = [
        log
        for log in ui_print_logs
        if "Release Bad" in str(log[0]) or "failed" in str(log[0]).lower()
    ]
    assert len(error_logs) >= 1, "Should log error for failed individual check"

    # Verify 1-second delays were called (3 delays for 3 checks - one after each)
    assert (
        sleep_calls.count(1) == 3
    ), "Should delay 1 second after each individual check"


def test_batch_check_error_object_triggers_fallback(monkeypatch):
    """Verify fallback triggered when batch returns error object (not None)."""
    realdebrid, ui_print_logs = _load_realdebrid_module(monkeypatch)

    # Create mock element with releases
    element = SimpleNamespace()
    element.Releases = [
        SimpleNamespace(hash="a" * 40, title="Release 1", files=[], cached=[]),
        SimpleNamespace(hash="b" * 40, title="Release 2", files=[], cached=[]),
    ]
    element.query = lambda: "test context"
    element.files = lambda: [".*"]  # Return wanted files pattern

    # Track get calls
    get_calls = []

    def mock_get(url, context=None):
        get_calls.append(url)
        # Return error object for batch (simulating 403 with error response)
        if "/" + "a" * 40 + "/" + "b" * 40 in url:
            # This simulates what happens when API returns {"error": "...", "error_code": 37}
            return SimpleNamespace(error="permission denied", error_code=37)
        # Return valid response for individual checks
        if url.endswith("a" * 40):
            response = SimpleNamespace()
            setattr(
                response,
                "a" * 40,
                SimpleNamespace(
                    rd=[
                        SimpleNamespace(
                            file1=SimpleNamespace(filename="test.mkv", filesize=1000)
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
                            file1=SimpleNamespace(filename="test2.mkv", filesize=2000)
                        )
                    ]
                ),
            )
            return response
        return None

    monkeypatch.setattr(realdebrid, "get", mock_get)

    # Mock time.sleep to track delay calls
    import time

    sleep_calls = []

    def mock_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(time, "sleep", mock_sleep)

    # Clear logs before check
    ui_print_logs.clear()

    # Run check
    realdebrid.check(element)

    # Verify batch endpoint was called first
    assert len(get_calls) >= 1
    assert "a" * 40 + "/" + "b" * 40 in get_calls[0]

    # Verify fallback message was logged
    fallback_logs = [
        log for log in ui_print_logs if "checking hashes individually" in str(log[0])
    ]
    assert len(fallback_logs) == 1, "Should log fallback message when batch returns error"

    # Verify individual checks were made
    individual_calls = [
        url for url in get_calls[1:] if url.endswith("a" * 40) or url.endswith("b" * 40)
    ]
    assert len(individual_calls) == 2, "Should check both hashes individually"

    # Verify 1-second delay was called twice (after each individual check)
    assert (
        sleep_calls.count(1) == 2
    ), "Should delay 1 second after each individual check"

    # Verify both releases have cached results
    cached_releases = [r for r in element.Releases if len(r.cached) > 0]
    assert len(cached_releases) == 2, "Both releases should be marked as cached after fallback"


def test_response_namespace_accumulation(monkeypatch):
    """Verify individual responses accumulate correctly into response namespace."""
    realdebrid, ui_print_logs = _load_realdebrid_module(monkeypatch)

    # Create mock element
    element = SimpleNamespace()
    element.Releases = [
        SimpleNamespace(hash="a" * 40, title="Release 1", files=[], cached=[]),
        SimpleNamespace(hash="b" * 40, title="Release 2", files=[], cached=[]),
    ]
    element.query = lambda: "test context"
    element.files = lambda: [".*"]  # Return wanted files pattern

    get_responses = []

    def mock_get(url, context=None):
        # Return None for batch
        if "/" + "a" * 40 in url and "/" + "b" * 40 in url:
            return None
        # Individual checks return valid responses
        if url.endswith("a" * 40):
            response = SimpleNamespace()
            setattr(
                response,
                "a" * 40,
                SimpleNamespace(
                    rd=[
                        SimpleNamespace(
                            file1=SimpleNamespace(filename="test1.mkv", filesize=1000)
                        )
                    ]
                ),
            )
            get_responses.append(("a", response))
            return response
        if url.endswith("b" * 40):
            response = SimpleNamespace()
            setattr(
                response,
                "b" * 40,
                SimpleNamespace(
                    rd=[
                        SimpleNamespace(
                            file1=SimpleNamespace(filename="test2.mkv", filesize=2000)
                        )
                    ]
                ),
            )
            get_responses.append(("b", response))
            return response
        return None

    monkeypatch.setattr(realdebrid, "get", mock_get)

    # Mock time.sleep to track delay calls
    import time

    sleep_calls = []

    def mock_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(time, "sleep", mock_sleep)

    # Run check
    realdebrid.check(element)

    # Verify both individual responses were collected
    assert len(get_responses) == 2
    assert get_responses[0][0] == "a"
    assert get_responses[1][0] == "b"

    # Verify both releases have cached results
    cached_releases = [r for r in element.Releases if len(r.cached) > 0]
    assert len(cached_releases) == 2, "Both releases should be marked as cached"

    # Verify 1-second delay was called twice (after each of 2 individual checks)
    assert (
        sleep_calls.count(1) == 2
    ), "Should delay 1 second after each individual check"
