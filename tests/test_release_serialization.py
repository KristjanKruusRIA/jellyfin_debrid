from types import SimpleNamespace

from frontend_jobs import serialize_release


def _make_release(**overrides):
    base = {
        "title": "Some Release 1080p",
        "source": "[aiostreams]",
        "type": "magnet",
        "size": 12.3456,
        "seeders": "42",
        "resolution": "1080",
        "cached": [],
        "files": [
            {"id": "1", "path": "video.mkv", "size": 1024},
            {"id": "2", "path": "sample.mkv", "size": 128},
        ],
        "wanted": 3,
        "unwanted": 1,
        "download": ["magnet:?xt=urn:btih:abc&dn=Some.Release"],
        "hash": "abc123",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_release_serializer_exposes_safe_summary_fields_only():
    release_obj = _make_release()

    serialized = serialize_release(release_obj, index=0)

    assert set(serialized.keys()) == {
        "release_id",
        "title",
        "source",
        "type",
        "size_gb",
        "seeders",
        "resolution",
        "cached",
        "cached_via",
        "file_count",
        "wanted",
        "unwanted",
        "encode",
        "codec",
        "hdr_tags",
        "audio",
        "channels",
        "group",
    }
    assert serialized["release_id"] == "0"
    assert "download" not in serialized
    assert "hash" not in serialized
    assert "files" not in serialized


def test_release_serializer_marks_cached_status_and_counts_files():
    release_obj = _make_release(
        cached=["realdebrid", "otherdebrid"],
        files=[
            {"id": "1", "path": "one.mkv", "size": 111},
            {"id": "2", "path": "two.mkv", "size": 222},
            {"id": "3", "path": "three.mkv", "size": 333},
        ],
    )

    serialized = serialize_release(release_obj, index=7)

    assert serialized["release_id"] == "7"
    assert serialized["cached"] is True
    assert serialized["cached_via"] == ["realdebrid", "otherdebrid"]
    assert serialized["file_count"] == 3
    assert serialized["size_gb"] == 12.35
    assert serialized["seeders"] == 42
    assert serialized["wanted"] == 3
    assert serialized["unwanted"] == 1
