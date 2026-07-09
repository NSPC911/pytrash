from typing import Protocol
from os import PathLike


class RecycleBin(Protocol):
    def recycle(self, items: list[str | PathLike]) -> None:
        """Recycle the given items.

        Args:
            items (list[str | PathLike]): A list of file paths to recycle.
        """
        ...

    def entries(self) -> list:
        """Get the list of entries in the recycle bin.

        Returns:
            list[str]: A list of file paths in the recycle bin.
        """
        ...

    def restore(self, items: list) -> None:
        """Restore the given items from the recycle bin.

        Args:
            items (list[str | PathLike]): A list of file paths to restore.
        """
        ...
