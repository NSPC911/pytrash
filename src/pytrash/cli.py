"""Command-line interface for pytrash."""

from __future__ import annotations

import argparse
import json
import sys
from os import PathLike

from pytrash import entries, recycle, restore


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""  # noqa: DOC201
    parser = argparse.ArgumentParser(
        description="pytrash: Cross-platform recycle bin management"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Trash command
    trash_parser = subparsers.add_parser("trash", help="Move files to trash")
    trash_parser.add_argument(
        "files",
        nargs="+",
        help="Files to move to trash",
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List trashed files")
    list_parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output as JSON",
    )

    # Entries command (alias for list)
    entries_parser = subparsers.add_parser("entries", help="List trashed files")
    entries_parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output as JSON",
    )

    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore files from trash")
    restore_parser.add_argument(
        "files",
        nargs="+",
        help="Files to restore (use names from 'list' command)",
    )

    return parser.parse_args()


def trash_files(files: list[str | PathLike]) -> None:
    """Move files to trash."""
    try:
        recycle(files)
        print(f"Moved {len(files)} file(s) to trash")
    except Exception as e:
        print(f"Error trashing files: {e}", file=sys.stderr)
        sys.exit(1)


def list_files(json_output: bool = False) -> None:
    """List files in trash."""
    try:
        trash_entries = entries()
        if json_output:
            # Convert TrashEntry objects to dict for JSON serialization
            entries_dict = []
            for entry in trash_entries:
                entry_dict = {
                    "name": entry.name,
                    "original_path": entry.original_path,
                    "deleted_at": entry.deleted_at.isoformat()
                    if entry.deleted_at
                    else None,
                    "size": entry.size,
                }
                entries_dict.append(entry_dict)
            print(json.dumps(entries_dict, indent=2))
        else:
            if not trash_entries:
                print("No files in trash")
                return

            for entry in trash_entries:
                when = entry.deleted_at.isoformat() if entry.deleted_at else "?"
                original = entry.original_path or "?"
                print(f"{when}\t{original}\t{entry.name}")
    except Exception as e:
        print(f"Error listing files: {e}", file=sys.stderr)
        sys.exit(1)


def restore_files(files: list[str]) -> None:
    """Restore files from trash."""
    try:
        # Get all entries to find matches
        all_entries = entries()
        entries_to_restore = []

        for file_pattern in files:
            # Match by name or original path
            matched_entries = [
                entry
                for entry in all_entries
                if (
                    entry.name == file_pattern
                    or (
                        entry.original_path
                        and entry.original_path.endswith(file_pattern)
                    )
                )
            ]

            if not matched_entries:
                print(
                    f"Warning: No trash entry found for '{file_pattern}'",
                    file=sys.stderr,
                )
                continue

            entries_to_restore.extend(matched_entries)

        if not entries_to_restore:
            print("No files matched for restoration", file=sys.stderr)
            return

        restore(entries_to_restore)
        print(f"Restored {len(entries_to_restore)} file(s)")

    except Exception as e:
        print(f"Error restoring files: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    args = parse_args()

    if args.command == "trash":
        trash_files(args.files)
    elif args.command == "list" or args.command == "entries":
        list_files(args.json)
    elif args.command == "restore":
        restore_files(args.files)


if __name__ == "__main__":
    main()
