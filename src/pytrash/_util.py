"""Small filesystem helpers shared across backends."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable


class RestoreConflictError(FileExistsError):
    """Destination paths blocking a restore."""

    def __init__(self, paths: list[str]) -> None:
        self.paths = paths
        super().__init__("Restore blocked by existing paths:\n" + "\n".join(paths))


def restore_paths(
    pairs: list[tuple[str, str]],
    on_exist: Callable[[Exception], bool],
    on_restored: Callable[[str], None] = lambda src: None,
) -> None:
    """Check an entire batch before merging it, retaining unmoved sources.

    Conflicts raise RestoreConflictError; filesystem failures propagate.

    Raises:
        FileNotFoundError: A source is missing.
    """
    planned: dict[str, bool] = {}
    conflicts: dict[str, None] = {}

    def scan(src: str, dest: str) -> None:
        directory = os.path.isdir(src) and not os.path.islink(src)
        key = os.path.normcase(os.path.abspath(dest))
        parent = os.path.dirname(dest)
        while parent and os.path.dirname(parent) != parent:
            parent_key = os.path.normcase(os.path.abspath(parent))
            if (
                os.path.lexists(parent)
                and (not os.path.isdir(parent) or os.path.islink(parent))
            ) or (parent_key in planned and not planned[parent_key]):
                conflicts[parent] = None
                return
            parent = os.path.dirname(parent)
        existing_dir = os.path.isdir(dest) and not os.path.islink(dest)
        if (os.path.lexists(dest) and not (directory and existing_dir)) or (
            key in planned and not (directory and planned[key])
        ):
            conflicts[dest] = None
        planned[key] = directory
        if directory:
            with os.scandir(src) as children:
                for child in children:
                    scan(child.path, os.path.join(dest, child.name))

    for src, dest in pairs:
        if not os.path.lexists(src):
            raise FileNotFoundError(f"trashed data missing: {src}")
        scan(src, dest)
    if conflicts:
        exc = RestoreConflictError(list(conflicts))
        if not on_exist(exc):
            raise exc

    def move(src: str, dest: str) -> None:
        parent = os.path.dirname(dest)
        while parent and os.path.dirname(parent) != parent:
            if os.path.islink(parent):
                raise RestoreConflictError([parent])
            parent = os.path.dirname(parent)
        directory = os.path.isdir(src) and not os.path.islink(src)
        if os.path.lexists(dest) and not (
            directory and os.path.isdir(dest) and not os.path.islink(dest)
        ):
            exc = RestoreConflictError([dest])
            if not on_exist(exc):
                raise exc
            remove_path(dest)
        if directory:
            created = not os.path.lexists(dest)
            os.makedirs(dest, exist_ok=True)
            if os.path.islink(dest):
                raise RestoreConflictError([dest])
            with os.scandir(src) as children:
                for child in children:
                    move(child.path, os.path.join(dest, child.name))
            if created:
                shutil.copystat(src, dest)
            os.rmdir(src)
        elif os.path.islink(src):
            os.symlink(os.readlink(src), dest, target_is_directory=os.path.isdir(src))
            os.unlink(src)
        else:
            # Exclusive creation prevents a late-arriving file from being overwritten.
            with open(src, "rb") as source, open(dest, "xb") as target:
                try:
                    shutil.copyfileobj(source, target)
                except BaseException:
                    target.close()
                    os.unlink(dest)
                    raise
            try:
                shutil.copystat(src, dest)
            except OSError:
                os.unlink(dest)
                raise
            os.unlink(src)

    for src, dest in pairs:
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        move(src, dest)
        on_restored(src)


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
