"""Command-line interface for pytrash."""

from __future__ import annotations

import argparse
import json
import sys

from pytrash import empty, entries, purge, recycle, restore


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

    # Purge command (permanent delete of specific items)
    purge_parser = subparsers.add_parser(
        "purge", help="Permanently delete files from trash (irreversible)"
    )
    purge_parser.add_argument(
        "files",
        nargs="+",
        help="Files to purge (use names from 'list' command)",
    )
    purge_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Do not ask for confirmation",
    )

    # Empty command (permanent delete of everything)
    empty_parser = subparsers.add_parser(
        "empty", help="Permanently delete everything in trash (irreversible)"
    )
    empty_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Do not ask for confirmation",
    )

    return parser.parse_args()


def trash_files(files: list[str]) -> None:
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


def _confirm(prompt: str) -> bool:
    """Ask the user to confirm a destructive action."""  # noqa: DOC201
    try:
        return input(f"{prompt} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False
    except KeyboardInterrupt:
        return False


def purge_files(files: list[str], assume_yes: bool = False) -> None:
    """Permanently delete matching files from trash."""
    try:
        all_entries = entries()
        to_purge = []
        for file_pattern in files:
            matched = [
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
            if not matched:
                print(
                    f"Warning: No trash entry found for '{file_pattern}'",
                    file=sys.stderr,
                )
                continue
            to_purge.extend(matched)

        if not to_purge:
            print("No files matched for purge", file=sys.stderr)
            return

        if not assume_yes and not _confirm(
            f"Permanently delete {len(to_purge)} file(s)? This cannot be undone."
        ):
            print("Aborted")
            return

        purge(to_purge)
        print(f"Purged {len(to_purge)} file(s)")
    except Exception as e:
        print(f"Error purging files: {e}", file=sys.stderr)
        sys.exit(1)


def empty_trash(assume_yes: bool = False) -> None:
    """Permanently delete everything in trash."""
    try:
        count = len(entries())
        if count == 0:
            print("No files in trash")
            return
        if not assume_yes and not _confirm(
            f"Permanently delete all {count} file(s)? This cannot be undone."
        ):
            print("Aborted")
            return
        empty()
        print(f"Emptied trash ({count} file(s))")
    except Exception as e:
        print(f"Error emptying trash: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    args = parse_args()

    match args.command:
        case "trash":
            trash_files(args.files)
        case "list" | "entries":
            list_files(args.json)
        case "restore":
            restore_files(args.files)
        case "purge":
            purge_files(args.files, args.yes)
        case "empty":
            empty_trash(args.yes)


if __name__ == "__main__":
    main()
