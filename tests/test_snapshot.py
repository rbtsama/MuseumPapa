import json
from pathlib import Path
from malibbene.common.snapshot import archive_raw_to_snapshot

def test_archive_copies_all_raw_to_dated_dir(tmp_path):
    raw = tmp_path / "raw"
    (raw / "assabet/catalog").mkdir(parents=True)
    (raw / "assabet/catalog" / "wakefield.json").write_text(json.dumps({"x": 1}))

    snapshots = tmp_path / "snapshots"
    result = archive_raw_to_snapshot(raw_root=raw, snapshot_root=snapshots, snapshot_date="2026-05-20")

    expected = snapshots / "2026-05-20" / "assabet" / "catalog" / "wakefield.json"
    assert expected.exists()
    assert json.loads(expected.read_text()) == {"x": 1}
    assert result["files_copied"] == 1

def test_archive_refuses_to_overwrite_existing_snapshot(tmp_path):
    raw = tmp_path / "raw"; raw.mkdir()
    snap = tmp_path / "snapshots/2026-05-20"; snap.mkdir(parents=True)
    (snap / "marker").write_text("existing")
    import pytest
    with pytest.raises(FileExistsError):
        archive_raw_to_snapshot(raw_root=raw, snapshot_root=tmp_path/"snapshots", snapshot_date="2026-05-20")
