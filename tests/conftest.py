"""Shared fixtures for the recycle-bin tests.

Every test here runs against a throwaway trash directory, never the real one.
Two things are redirected to make that true:

* `XDG_DATA_HOME`, which decides where the home trash lives, and
* `LinuxRecycleBin._all_trash_dirs`, which normally scans every mount point for
  a `.Trash-$uid`. Left alone, `entries()` would list the user's actual trashed
  files and `empty()` would destroy them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

if not sys.platform.startswith("linux"):  # pragma: no cover - backend is per-OS
    pytest.skip("freedesktop backend", allow_module_level=True)

from pytrash import _linux  # noqa: E402


@pytest.fixture
def trash_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the trash into a throwaway directory.

    Returns:
        The isolated `$XDG_DATA_HOME/Trash` the tests recycle into.
    """
    data_home = tmp_path / "xdg"
    data_home.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setattr(
        _linux.LinuxRecycleBin,
        "_all_trash_dirs",
        lambda self: [_linux._home_trash()],
    )
    return data_home / "Trash"


@pytest.fixture
def bin(trash_dir: Path) -> _linux.LinuxRecycleBin:
    """Build a bin pointed at the isolated trash.

    Returns:
        A recycle bin wired to the isolated trash directory.
    """
    return _linux.LinuxRecycleBin()


@pytest.fixture
def work(tmp_path: Path) -> Path:
    """Somewhere to create the files that get recycled.

    It sits under the same `tmp_path` as the trash, so both are on one
    filesystem and items land in the home trash rather than a `.Trash-$uid`.

    Returns:
        A directory to create the files that get recycled.
    """
    d = tmp_path / "work"
    d.mkdir()
    return d
