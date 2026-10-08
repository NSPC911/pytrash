from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

if sys.platform != "win32":  # pragma: no cover - backend is per-OS
    pytest.skip("windows backend", allow_module_level=True)

from pytrash import RestoreConflictError
from pytrash._windows import WindowsRecycleBin


def _write_i_file(path: Path, original: str, size: int = 1) -> None:
    encoded = (original + "\x00").encode("utf-16-le")
    raw = encoded + (b"\x00" * max(0, 520 - len(encoded)))
    blob = struct.pack("<qqq", 1, size, 1) + raw
    path.write_bytes(blob)


def test_entries_drops_orphaned_info_sidecar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sid_dir = tmp_path / "S-1-5-21-test"
    sid_dir.mkdir()
    info = sid_dir / "$IABCDEF"
    _write_i_file(info, str(tmp_path / "work" / "ghost.txt"))

    bin = WindowsRecycleBin()
    monkeypatch.setattr(WindowsRecycleBin, "_sid_dirs", lambda self: [str(sid_dir)])

    assert bin.entries() == []
    assert not info.exists()


def test_entries_keeps_valid_pair(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sid_dir = tmp_path / "S-1-5-21-test"
    sid_dir.mkdir()
    info = sid_dir / "$IABCDEF"
    data = sid_dir / "$RABCDEF"
    original = tmp_path / "work" / "notes.txt"
    _write_i_file(info, str(original), size=42)
    data.write_text("payload")

    bin = WindowsRecycleBin()
    monkeypatch.setattr(WindowsRecycleBin, "_sid_dirs", lambda self: [str(sid_dir)])

    (entry,) = bin.entries()
    assert entry.name == "notes.txt"
    assert entry.original_path == str(original)
    assert entry.size == 42
    assert entry._handle == str(info)
    assert info.exists()


def test_restore_merges_only_after_conflicts_are_resolved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sid_dir = tmp_path / "S-1-5-21-test"
    sid_dir.mkdir()
    info = sid_dir / "$IABCDEF"
    data = sid_dir / "$RABCDEF"
    original = tmp_path / "work" / "project"
    _write_i_file(info, str(original), size=0)
    data.mkdir()
    (data / "child").write_text("trashed")
    original.mkdir(parents=True)
    (original / "child").write_text("live")
    bin = WindowsRecycleBin()
    monkeypatch.setattr(WindowsRecycleBin, "_sid_dirs", lambda self: [str(sid_dir)])
    with pytest.raises(RestoreConflictError) as caught:
        bin.restore(bin.entries())
    assert caught.value.paths == [str(original / "child")]
    assert info.exists() and (data / "child").exists()
    (original / "child").unlink()
    (original / "keep").write_text("keep")
    bin.restore(bin.entries())
    assert (original / "child").read_text() == "trashed"
    assert (original / "keep").read_text() == "keep"
    assert not info.exists() and not data.exists()


def test_entries_recursive_lists_files_inside_trashed_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sid_dir = tmp_path / "S-1-5-21-test"
    sid_dir.mkdir()
    info = sid_dir / "$IABCDEF"
    data = sid_dir / "$RABCDEF"
    original = tmp_path / "work" / "project"
    _write_i_file(info, str(original), size=0)
    (data / "src").mkdir(parents=True)
    (data / "README.md").write_text("readme")
    (data / "src" / "main.py").write_text("print()")

    bin = WindowsRecycleBin()
    monkeypatch.setattr(WindowsRecycleBin, "_sid_dirs", lambda self: [str(sid_dir)])

    entries = sorted(bin.entries(recursive=True), key=lambda entry: entry.name)

    assert [entry.name for entry in entries] == [
        "project\\README.md",
        "project\\src\\main.py",
    ]
    assert [entry.original_path for entry in entries] == [
        str(original / "README.md"),
        str(original / "src" / "main.py"),
    ]
    assert [entry._handle for entry in entries] == [
        str(data / "README.md"),
        str(data / "src" / "main.py"),
    ]
