"""Sending things to the bin.

Mirrors the `delete`/`delete_all` tests in trash-rs (`tests/trash.rs`,
`tests/isolated.rs`): the item leaves its original path, whatever kind of item
it is, and a bad request leaves the filesystem untouched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytrash._linux import LinuxRecycleBin


def test_recycles_a_file(bin: LinuxRecycleBin, work: Path, trash_dir: Path) -> None:
    f = work / "notes.txt"
    f.write_text("hello")

    bin.recycle([str(f)])

    assert not f.exists()
    assert (trash_dir / "files" / "notes.txt").read_text() == "hello"


def test_recycles_a_folder_with_contents(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    folder = work / "project"
    (folder / "src").mkdir(parents=True)
    (folder / "src" / "main.py").write_text("print()")

    bin.recycle([str(folder)])

    assert not folder.exists()
    assert (
        trash_dir / "files" / "project" / "src" / "main.py"
    ).read_text() == "print()"


def test_recycles_several_items_at_once(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    files = []
    for i in range(3):
        f = work / f"file{i}.txt"
        f.write_text(str(i))
        files.append(f)

    bin.recycle([str(f) for f in files])

    assert not any(f.exists() for f in files)
    assert sorted(p.name for p in (trash_dir / "files").iterdir()) == [
        "file0.txt",
        "file1.txt",
        "file2.txt",
    ]


def test_recycles_a_symlink_without_following_it(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    target = work / "target.txt"
    target.write_text("still here")
    link = work / "link.txt"
    link.symlink_to(target)

    bin.recycle([str(link)])

    assert not link.is_symlink()
    assert target.read_text() == "still here"  # the link went, the target stayed
    trashed = trash_dir / "files" / "link.txt"
    assert trashed.is_symlink()
    assert trashed.readlink() == target


def test_recycles_a_folder_containing_a_symlink(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    target = work / "target.txt"
    target.write_text("still here")
    folder = work / "folder"
    folder.mkdir()
    (folder / "link.txt").symlink_to(target)

    bin.recycle([str(folder)])

    assert not folder.exists()
    assert target.read_text() == "still here"
    assert (trash_dir / "files" / "folder" / "link.txt").is_symlink()


def test_recycles_a_deeply_nested_tree(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    deep = work / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / "leaf.txt").write_text("leaf")

    bin.recycle([str(work / "a")])

    assert not (work / "a").exists()
    assert (trash_dir / "files" / "a" / "b" / "c" / "leaf.txt").read_text() == "leaf"


def test_recycles_a_relative_path(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (work / "here.txt").write_text("x")
    monkeypatch.chdir(work)

    bin.recycle(["here.txt"])

    assert not (work / "here.txt").exists()
    info = (trash_dir / "info" / "here.txt.trashinfo").read_text()
    assert f"Path={work}/here.txt" in info  # recorded absolute, not relative


def test_missing_path_raises_and_trashes_nothing(
    bin: LinuxRecycleBin, work: Path, trash_dir: Path
) -> None:
    with pytest.raises(FileNotFoundError):
        bin.recycle([str(work / "ghost.txt")])

    assert not trash_dir.exists()


def test_empty_path_is_rejected(
    bin: LinuxRecycleBin, work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # "" resolves to the cwd, so accepting it would recycle the working
    # directory. trash-rs rejects it outright; so do we.
    monkeypatch.chdir(work)
    (work / "bystander.txt").write_text("x")

    with pytest.raises(ValueError, match="empty path"):
        bin.recycle([""])

    assert (work / "bystander.txt").exists()


def test_recycle_rejects_a_bare_string(bin: LinuxRecycleBin, work: Path) -> None:
    # A str is iterable, so without the check this would recycle one item per
    # character.
    f = work / "f.txt"
    f.write_text("x")

    with pytest.raises(TypeError):
        bin.recycle(str(f))  # ty: ignore[invalid-argument-type]

    assert f.exists()


def test_recycling_nothing_is_a_no_op(bin: LinuxRecycleBin, trash_dir: Path) -> None:
    bin.recycle([])

    assert not trash_dir.exists()
