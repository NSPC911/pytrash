"""Conformance with the FreeDesktop.org trash spec.

The Linux backend is not a wrapper around a system call: it *is* the spec --
a `files/` directory, an `info/` directory, and one `.trashinfo` sidecar per
item. These tests pin the on-disk format, and (like trash-rs's
`freedesktop_tests.rs`) the behaviour when the trash directory is not the plain
directory it is supposed to be.

https://specifications.freedesktop.org/trash-spec/latest/
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from pytrash._linux import LinuxRecycleBin


def test_trashinfo_format(bin: LinuxRecycleBin, work: Path, trash_dir: Path) -> None:
    f = work / "notes.txt"
    f.write_text("x")
    before = datetime.now().replace(microsecond=0)

    bin.recycle([str(f)])

    lines = (trash_dir / "info" / "notes.txt.trashinfo").read_text().splitlines()
    assert lines[0] == "[Trash Info]"
    assert lines[1] == f"Path={work}/notes.txt"
    deleted_at = datetime.strptime(
        lines[2].removeprefix("DeletionDate="), "%Y-%m-%dT%H:%M:%S"
    )
    assert before <= deleted_at <= datetime.now()


def test_trashinfo_percent_encodes_the_path(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    f = work / "a file #1 100%.txt"
    f.write_text("x")

    bin.recycle([str(f)])

    info = (trash_dir / "info" / "a file #1 100%.txt.trashinfo").read_text()
    assert "a%20file%20%231%20100%25.txt" in info
    assert f"Path={work}/" in info  # separators stay literal, only the rest is quoted
    # ...and it survives the round trip back out through entries().
    (entry,) = bin.entries()
    assert entry.original_path == str(f)


def test_names_with_unicode_round_trip(bin: LinuxRecycleBin, work: Path) -> None:
    f = work / "日本語 – файл.txt"
    f.write_text("x")

    bin.recycle([str(f)])
    (entry,) = bin.entries()

    assert entry.name == "日本語 – файл.txt"
    assert entry.original_path == str(f)


def test_creates_the_trash_directories_on_demand(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    assert not trash_dir.exists()
    (work / "f.txt").write_text("x")

    bin.recycle([str(work / "f.txt")])

    assert (trash_dir / "files").is_dir()
    assert (trash_dir / "info").is_dir()


def test_same_name_twice_does_not_clobber(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    # The spec forbids overwriting an existing entry, so the second `notes.txt`
    # has to be stored under a name of its own.
    for i, sub in enumerate(("one", "two")):
        (work / sub).mkdir()
        (work / sub / "notes.txt").write_text(str(i))
        bin.recycle([str(work / sub / "notes.txt")])

    assert (trash_dir / "files" / "notes.txt").read_text() == "0"
    assert (trash_dir / "files" / "notes.1.txt").read_text() == "1"
    assert (trash_dir / "info" / "notes.1.txt.trashinfo").exists()
    # Both keep their own origin, which is what lets restore put them back.
    origins = {e.name: e.original_path for e in bin.entries()}
    assert origins == {
        "notes.txt": f"{work}/one/notes.txt",
        "notes.1.txt": f"{work}/two/notes.txt",
    }


def test_collision_suffix_goes_before_the_extension(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    # The counter goes before the last extension only, so a double extension
    # like .tar.gz keeps just the .gz on the end.
    for sub in ("one", "two", "three"):
        (work / sub).mkdir()
        (work / sub / "archive.tar.gz").write_text(sub)
        bin.recycle([str(work / sub / "archive.tar.gz")])

    names = sorted(p.name for p in (trash_dir / "files").iterdir())
    assert names == ["archive.tar.1.gz", "archive.tar.2.gz", "archive.tar.gz"]


def test_entries_ignores_files_that_are_not_sidecars(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    (work / "f.txt").write_text("x")
    bin.recycle([str(work / "f.txt")])
    (trash_dir / "info" / "stray.txt").write_text("not a sidecar")

    assert [e.name for e in bin.entries()] == ["f.txt"]


def test_entries_skips_a_sidecar_with_no_path(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    (work / "f.txt").write_text("x")
    bin.recycle([str(work / "f.txt")])
    (trash_dir / "info" / "broken.trashinfo").write_text(
        "[Trash Info]\nDeletionDate=2026-01-01T00:00:00\n"
    )

    # Without an origin there is nowhere to restore it to, so it is not an entry.
    assert [e.name for e in bin.entries()] == ["f.txt"]


def test_entries_tolerates_an_unparseable_date(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    (trash_dir / "info").mkdir(parents=True)
    (trash_dir / "files").mkdir()
    (trash_dir / "files" / "old.txt").write_text("x")
    (trash_dir / "info" / "old.txt.trashinfo").write_text(
        f"[Trash Info]\nPath={work}/old.txt\nDeletionDate=whenever\n"
    )

    (entry,) = bin.entries()

    assert entry.original_path == f"{work}/old.txt"
    assert entry.deleted_at is None  # listable, just undated


def test_trash_directory_that_is_a_symlink_to_a_directory(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path, tmp_path: Path
) -> None:
    real = tmp_path / "real-trash"
    real.mkdir()
    trash_dir.parent.mkdir(exist_ok=True)
    trash_dir.symlink_to(real)
    (work / "f.txt").write_text("x")

    bin.recycle([str(work / "f.txt")])

    assert (real / "files" / "f.txt").read_text() == "x"


@pytest.mark.parametrize("kind", ["file", "symlink_to_file", "broken_symlink"])
def test_unusable_trash_directory_fails_without_losing_the_file(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path, tmp_path: Path, kind: str
) -> None:
    trash_dir.parent.mkdir(exist_ok=True)
    if kind == "file":
        trash_dir.write_text("i am not a directory")
    elif kind == "symlink_to_file":
        decoy = tmp_path / "decoy"
        decoy.write_text("x")
        trash_dir.symlink_to(decoy)
    else:
        trash_dir.symlink_to(tmp_path / "nowhere")

    f = work / "f.txt"
    f.write_text("precious")

    with pytest.raises(OSError):
        bin.recycle([str(f)])

    assert f.read_text() == "precious"  # the file is still where it was
