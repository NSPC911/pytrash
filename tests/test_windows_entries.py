from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

if sys.platform != "win32":  # pragma: no cover - backend is per-OS
    pytest.skip("windows backend", allow_module_level=True)

from pytrash._windows import WindowsRecycleBin


def _write_i_file(path: Path, original: str, size: int = 1) -> None:
    encoded = (original + "\x00").encode("utf-16-le")
    raw = encoded + (b"\x00" * max(0, 520 - len(encoded)))
    blob = struct.pack("<qqq", 1, size, 1) + raw
    path.write_bytes(blob)


def test_entries_drops_orphaned_info_sidecar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sid_dir = tmp_path / "S-1-5-21-test"
    sid_dir.mkdir()
    info = sid_dir / "$IABCDEF"
    _write_i_file(info, str(tmp_path / "work" / "ghost.txt"))

    bin = WindowsRecycleBin()
    monkeypatch.setattr(WindowsRecycleBin, "_sid_dirs", lambda self: [str(sid_dir)])

    assert bin.entries() == []
    assert not info.exists()


def test_entries_keeps_valid_pair(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
