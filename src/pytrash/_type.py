from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal, Protocol, overload, runtime_checkable


@dataclass(frozen=True)
class TrashEntry:
    """A single item currently sitting in the recycle bin.

    Instances are produced by `RecycleBin.entries` and consumed by
    `RecycleBin.restore`. The `_handle` field is backend-private
    (a `.trashinfo` path on Linux, an `$I` path on Windows, ...) and is
    what actually lets restore find the trashed bytes; do not construct it
    yourself.
    """

    name: str
    """Human-facing name of the item as it appears in the bin."""

    original_path: str | None
    """Absolute path the item lived at before it was recycled. None if the platform does not record it."""

    deleted_at: datetime | None
    """When the item was recycled, if the platform records it."""

    size: int | None = None
    """Size in bytes of the original item, if known."""

    is_dir: bool = False
    """Whether the trashed item was a directory (True) or a file (False)."""

    _handle: str = field(default="", repr=False)
    """Backend-private locator for the trashed data. Not part of the API."""


@runtime_checkable
class RecycleBinLike(Protocol):
    """Cross-platform recycle-bin backend contract.

    One concrete implementation exists per OS. Callers should go through the
    module-level helpers in `pytrash` rather than instantiating a backend
    directly.
    """

    @overload
    def recycle(self, items: list[str]) -> None: ...

    @overload
    def recycle(
        self, items: list[str], return_entries: Literal[True]
    ) -> list[TrashEntry]: ...

    @overload
    def recycle(self, items: list[str], return_entries: Literal[False]) -> None: ...

    def recycle(
        self, items: list[str], return_entries: bool = False
    ) -> list[TrashEntry] | None:
        """Move the given items to the recycle bin.

        Args:
            items: File or directory paths to recycle.
            return_entries: Return the newly recycled entries when `True`.

        Returns:
            Entries suitable for `restore` when requested, otherwise `None`.
        """
        ...

    def entries(self, *, recursive: bool = False) -> list[TrashEntry]:
        """List everything currently in the recycle bin.

        Args:
            recursive: When `True`, backends may return items nested inside
                trashed directories instead of only top-level trashed items.

        Returns:
            The trashed items, most-recently-deleted first where the platform
            records deletion times.
        """
        ...

    def restore(
        self,
        items: list[TrashEntry],
        on_exist: Callable[[Exception], bool] = lambda x: False,
    ) -> None:
        """Restore items previously returned by `entries`.

        Args:
            items: Entries to move back to their original locations.
            on_exist: Optional callback allowing replacement of conflicting
                paths when it returns `True`. By default, all destinations
                are checked before anything moves and conflicts raise a
                `RestoreConflictError` with a `paths` list. Real directories
                merge recursively. Runtime failures can leave a partial
                restore; unmoved contents retain their trash metadata.
        """
        ...

    def purge(
        self,
        items: list[TrashEntry],
        on_error: Callable[[Exception], bool] = lambda e: False,
    ) -> None:
        """Permanently delete items previously returned by `entries`.

        This is irreversible: the trashed data is destroyed, not moved back.
        The data payload is removed before its metadata sidecar, so a failure
        partway through leaves the entry still listable rather than an
        invisible orphan taking up space.

        Args:
            items: Entries to delete for good.
            on_error: Optional callback invoked with any exception raised
                while purging an item. If it returns `True`, the purge
                continues with the next item; if `False`, it aborts and
                propagates the exception.
        """
        ...

    def empty(self, on_error: Callable[[Exception], bool] = lambda e: False) -> None:
        """Permanently delete everything currently in the recycle bin.

        Convenience for `purge(entries())`. Irreversible.

        Args:
            on_error: Callback forwarded to `purge`; see there.
        """
        ...
