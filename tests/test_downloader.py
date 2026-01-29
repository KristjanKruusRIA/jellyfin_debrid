import importlib.util
from pathlib import Path


def _load_module_from_path(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sanitize_filename_basic():
    repo_root = Path(__file__).resolve().parents[1]
    # stub ui.ui_print to avoid importing the whole ui/content graph
    import sys
    import types

    ui_print_stub = types.SimpleNamespace()
    ui_print_stub.ui_print = lambda *a, **k: None
    sys.modules["ui.ui_print"] = ui_print_stub
    sys.modules["ui"] = types.SimpleNamespace(ui_print=ui_print_stub)
    dl = _load_module_from_path(
        str(repo_root / "downloader" / "__init__.py"), "downloader_test"
    )
    # sanitizer removes invalid chars like ':' but preserves spaces
    assert dl.sanitize_filename("My Movie: The Return.mkv") == "My Movie The Return.mkv"


def test_sanitize_filename_edgecases():
    repo_root = Path(__file__).resolve().parents[1]
    import sys
    import types

    ui_print_stub = types.SimpleNamespace()
    ui_print_stub.ui_print = lambda *a, **k: None
    sys.modules["ui.ui_print"] = ui_print_stub
    sys.modules["ui"] = types.SimpleNamespace(ui_print=ui_print_stub)
    dl = _load_module_from_path(
        str(repo_root / "downloader" / "__init__.py"), "downloader_test"
    )
    assert dl.sanitize_filename("../secret/evil?.mkv") == "secret.evil.mkv"
