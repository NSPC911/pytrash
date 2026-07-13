"""Small filesystem helpers shared across backends."""

from __future__ import annotations

import os
import shutil


def source_path(item: object) -> str:
    """Absolute path of an item being recycled.

    Returns:
        `item` as an absolute path.

    Raises:
        ValueError: if `item` is the empty path, which `abspath` would
            otherwise resolve to the current working directory -- recycling
            the cwd instead of failing.
    """
    raw = os.fspath(item)  # ty: ignore[invalid-argument-type]
    if not raw:
        raise ValueError("cannot recycle an empty path")
    return os.path.abspath(raw)


def remove_path(path: str) -> None:
    """Permanently delete `path`, whatever it is.

    Directories are removed recursively; files and symlinks are unlinked.
    A path that is already gone is treated as success, so purging a
    half-deleted entry still converges.
    """
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except FileNotFoundError:
        pass
