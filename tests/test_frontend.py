"""Tests for frontend module import and service-mode wiring."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_frontend_module(monkeypatch):
    """Load frontend module with lightweight flask stubs."""
    repo_root = Path(__file__).resolve().parents[1]
    frontend_path = repo_root / "frontend.py"

    flask_stub = ModuleType("flask")

    class _Flask:
        def __init__(self, name):
            self.name = name

        def route(self, *_args, **_kwargs):
            def _decorator(fn):
                return fn

            return _decorator

        def run(self, *args, **kwargs):
            return None

    def _jsonify(payload):
        return payload

    def _render_template_string(template):
        return template

    setattr(flask_stub, "Flask", _Flask)
    setattr(flask_stub, "jsonify", _jsonify)
    setattr(flask_stub, "render_template_string", _render_template_string)

    monkeypatch.setitem(sys.modules, "flask", flask_stub)

    spec = importlib.util.spec_from_file_location("frontend_test", str(frontend_path))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frontend_module_imports_successfully(monkeypatch):
    """Verify frontend module imports and exposes start_frontend."""
    frontend = _load_frontend_module(monkeypatch)
    assert frontend is not None
    assert hasattr(frontend, "start_frontend")


def test_service_mode_uses_frontend_start_function():
    """Verify service mode imports and wires start_frontend as thread target."""
    repo_root = Path(__file__).resolve().parents[1]
    main_source = (repo_root / "main.py").read_text(encoding="utf-8")

    assert "from frontend import start_frontend" in main_source
    assert "target=start_frontend" in main_source
