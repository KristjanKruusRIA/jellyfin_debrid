import sys
import types
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import store


def test_store_save_load(tmp_path, monkeypatch):
    # create a minimal ui.ui_print module substitute to avoid importing the whole package
    ui_print = types.SimpleNamespace()
    ui_print.config_dir = str(tmp_path)

    def set_log_dir(cfg):
        ui_print.config_dir = cfg

    ui_print.set_log_dir = set_log_dir

    def ui_print_fn(s, *a, **kw):
        pass

    ui_print.ui_print = ui_print_fn

    # inject into sys.modules so store's local import resolves
    monkeypatch.setitem(sys.modules, "ui.ui_print", ui_print)

    data = [{"a": 1}, {"b": 2}]
    store.save(data, "mod", "var")
    loaded = store.load("mod", "var")
    assert loaded == data

    # cleanup
    (tmp_path / "mod_var.pkl").unlink() if (tmp_path / "mod_var.pkl").exists() else None
