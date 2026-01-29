import importlib.util
import os
import sys
import types
from pathlib import Path

repo_root = Path(__file__).resolve().parents[0]
aiostreams_path = repo_root / "scraper" / "services" / "aiostreams.py"

# Set environment variables before importing
os.environ["AIOSTREAMS_UUID"] = "X"
os.environ["AIOSTREAMS_B64CONFIG"] = "Y"

# stubs
releases_stub = types.SimpleNamespace()


class _Release:
    def __init__(self, source, type_, title, files, size, download, seeders=0):
        self.source = source
        self.type = type_
        self.title = title
        self.files = files
        self.size = size
        self.download = download
        self.seeders = seeders


releases_stub.release = _Release
sys.modules["releases"] = releases_stub
ui_print_stub = types.SimpleNamespace()
ui_print_stub.ui_settings = types.SimpleNamespace(debug=True)
ui_print_stub.ui_print = lambda *a, **k: print("UI_PRINT:", a, k)
sys.modules["ui.ui_print"] = ui_print_stub
services_stub = types.SimpleNamespace(active=["aiostreams"])
sys.modules["scraper.services"] = services_stub
sys.modules["scraper"] = types.SimpleNamespace(services=services_stub)
# load aiostreams
spec = importlib.util.spec_from_file_location("aiostreams_test", str(aiostreams_path))
aiostreams = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aiostreams)

# monkeypatch get
aiostreams.get = lambda url: types.SimpleNamespace(
    streams=[
        types.SimpleNamespace(url="http://example.com/movie.mkv", size="1073741824")
    ]
)
print("calling scrape")
res = aiostreams.scrape("tt0000001", "tt0000001")
print("scraped result:", res)
