"""Listing, restoring, purging and emptying.

This is the half of the API that trash-rs keeps behind `os_limited` (`list`,
`restore_all`, `purge_all`) and the reason pytrash exists, so it gets the same
treatment: the round trip, the empty-input no-ops, and the two ways a restore
can legitimately refuse -- a collision with a file that has since reappeared,
and twins that share a name.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import pytest

from pytrash._linux import LinuxRecycleBin


def make(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


# -- entries -------------------------------------------------------------------


def test_entries_reports_name_origin_size_and_time(
    bin: LinuxRecycleBin, work: Path
) -> None:
    f = make(work / "notes.txt", "12345")
    before = datetime.now().replace(microsecond=0)

    bin.recycle([str(f)])
    (entry,) = bin.entries()

    assert entry.name == "notes.txt"
    assert entry.original_path == str(f)
    assert entry.size == 5
    assert entry.deleted_at is not None
    assert before <= entry.deleted_at <= datetime.now()


def test_entries_is_empty_for_an_untouched_bin(bin: LinuxRecycleBin) -> None:
    assert bin.entries() == []


def test_entries_lists_most_recently_deleted_first(
    bin: LinuxRecycleBin, work: Path
) -> None:
    # DeletionDate has one-second resolution, so the deletions have to be
    # spaced out for the ordering to be observable at all.
    for name in ("first.txt", "second.txt"):
        bin.recycle([str(make(work / name))])
        time.sleep(1.1)

    assert [e.name for e in bin.entries()] == ["second.txt", "first.txt"]


def test_entries_survives_a_purged_data_file(bin: LinuxRecycleBin, work: Path) -> None:
    bin.recycle([str(make(work / "f.txt"))])
    (entry,) = bin.entries()
    Path(entry._handle.replace("/info/", "/files/").removesuffix(".trashinfo")).unlink()

    (entry,) = bin.entries()

    assert entry.size is None  # unknown, but still listed and still restorable


# -- restore -------------------------------------------------------------------


def test_restore_puts_a_file_back_with_its_contents(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    f = make(work / "notes.txt", "hello")
    bin.recycle([str(f)])

    bin.restore(bin.entries())

    assert f.read_text() == "hello"
    assert bin.entries() == []
    assert list((trash_dir / "files").iterdir()) == []
    assert list((trash_dir / "info").iterdir()) == []  # sidecar cleaned up too


def test_restore_puts_a_folder_back(bin: LinuxRecycleBin, work: Path) -> None:
    folder = work / "project"
    make(folder / "src" / "main.py", "print()")
    bin.recycle([str(folder)])

    bin.restore(bin.entries())

    assert (folder / "src" / "main.py").read_text() == "print()"


def test_restore_recreates_a_missing_parent_directory(
    bin: LinuxRecycleBin, work: Path
) -> None:
    f = make(work / "gone" / "notes.txt", "hello")
    bin.recycle([str(f)])
    (work / "gone").rmdir()

    bin.restore(bin.entries())

    assert f.read_text() == "hello"


def test_restore_of_nothing_is_a_no_op(bin: LinuxRecycleBin, work: Path) -> None:
    bin.recycle([str(make(work / "f.txt"))])

    bin.restore([])

    assert len(bin.entries()) == 1  # untouched


def test_restore_twins_go_back_to_their_own_origins(
    bin: LinuxRecycleBin, work: Path
) -> None:
    # Two different files with the same basename: the trash stores them as
    # notes.txt and notes.1.txt, but each must land back where it came from.
    one = make(work / "one" / "notes.txt", "one")
    two = make(work / "two" / "notes.txt", "two")
    bin.recycle([str(one), str(two)])
    assert not one.exists() and not two.exists()

    bin.restore(bin.entries())

    assert one.read_text() == "one"
    assert two.read_text() == "two"
    assert bin.entries() == []


def test_restore_refuses_to_overwrite_a_reappeared_file(
    bin: LinuxRecycleBin, work: Path
) -> None:
    f = make(work / "notes.txt", "trashed")
    bin.recycle([str(f)])
    make(work / "notes.txt", "recreated")  # something took the name back

    with pytest.raises(FileExistsError):
        bin.restore(bin.entries())

    assert f.read_text() == "recreated"  # the live file wins
    assert len(bin.entries()) == 1  # and the trashed copy is still there


def test_restore_overwrites_when_the_callback_allows_it(
    bin: LinuxRecycleBin, work: Path
) -> None:
    f = make(work / "notes.txt", "trashed")
    bin.recycle([str(f)])
    make(work / "notes.txt", "recreated")

    bin.restore(bin.entries(), on_exist=lambda exc: True)

    assert f.read_text() == "trashed"
    assert bin.entries() == []


def test_restore_of_a_vanished_data_file_raises(
    bin: LinuxRecycleBin, work: Path
) -> None:
    bin.recycle([str(make(work / "notes.txt"))])
    (entry,) = bin.entries()
    Path(entry._handle.replace("/info/", "/files/").removesuffix(".trashinfo")).unlink()

    with pytest.raises(FileNotFoundError):
        bin.restore([entry])


# -- purge and empty -----------------------------------------------------------


def test_purge_removes_the_data_and_the_sidecar(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    f = make(work / "notes.txt")
    bin.recycle([str(f)])

    bin.purge(bin.entries())

    assert bin.entries() == []
    assert list((trash_dir / "files").iterdir()) == []
    assert list((trash_dir / "info").iterdir()) == []
    assert not f.exists()  # purge destroys, it does not restore


def test_purge_removes_a_folder_recursively(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    make(work / "project" / "src" / "main.py")
    bin.recycle([str(work / "project")])

    bin.purge(bin.entries())

    assert bin.entries() == []
    assert list((trash_dir / "files").iterdir()) == []


def test_purge_leaves_the_other_entries_alone(bin: LinuxRecycleBin, work: Path) -> None:
    bin.recycle([str(make(work / "keep.txt")), str(make(work / "drop.txt"))])
    doomed = [e for e in bin.entries() if e.name == "drop.txt"]

    bin.purge(doomed)

    assert [e.name for e in bin.entries()] == ["keep.txt"]


def test_purge_of_nothing_is_a_no_op(bin: LinuxRecycleBin, work: Path) -> None:
    bin.recycle([str(make(work / "f.txt"))])

    bin.purge([])

    assert len(bin.entries()) == 1


def test_purge_is_idempotent(bin: LinuxRecycleBin, work: Path) -> None:
    bin.recycle([str(make(work / "f.txt"))])
    entries = bin.entries()

    bin.purge(entries)
    bin.purge(entries)  # same stale entries, already gone

    assert bin.entries() == []


def test_empty_clears_the_whole_bin(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    bin.recycle([str(make(work / f"f{i}.txt")) for i in range(3)])
    make(work / "folder" / "inner.txt")
    bin.recycle([str(work / "folder")])
    assert len(bin.entries()) == 4

    bin.empty()

    assert bin.entries() == []
    assert list((trash_dir / "files").iterdir()) == []
    assert list((trash_dir / "info").iterdir()) == []


def test_empty_on_an_empty_bin_is_a_no_op(bin: LinuxRecycleBin) -> None:
    bin.empty()

    assert bin.entries() == []


@pytest.mark.parametrize("method", ["restore", "purge"])
def test_they_reject_a_bare_entry(
    bin: LinuxRecycleBin, work: Path, method: str
) -> None:
    bin.recycle([str(make(work / "f.txt"))])
    (entry,) = bin.entries()

    with pytest.raises(TypeError):
        getattr(bin, method)(entry)  # not wrapped in a list

    assert len(bin.entries()) == 1
