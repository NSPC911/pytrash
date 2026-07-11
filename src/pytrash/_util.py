"""Small filesystem helpers shared across backends."""

from __future__ import annotations

import os
import shutil


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
