import builtins
from pathlib import Path

import pytest

from pytrash import RestoreConflictError
from pytrash._util import restore_paths


def test_merge_and_batch_conflicts(tmp_path: Path) -> None:
    source = tmp_path / "trash"
    dest = tmp_path / "destination"
    (source / "nested").mkdir(parents=True)
    (dest / "nested").mkdir(parents=True)
    (source / "nested" / "a").write_text("trashed")
    (source / "b").write_text("trashed")
    (dest / "nested" / "a").write_text("live")
    (dest / "b").write_text("live")
    extra = tmp_path / "extra"
    extra.write_text("extra")
    restored_extra = tmp_path / "restored-extra"

    with pytest.raises(RestoreConflictError) as caught:
        restore_paths(
            [(str(extra), str(restored_extra)), (str(source), str(dest))],
            lambda e: False,
        )
    assert set(caught.value.paths) == {str(dest / "nested" / "a"), str(dest / "b")}
    assert extra.exists() and not restored_extra.exists()
    assert (source / "b").read_text() == "trashed"
    (dest / "nested" / "a").unlink()
    (dest / "b").unlink()
    (dest / "keep").write_text("keep")
    restore_paths([(str(source), str(dest))], lambda e: False)
    assert not source.exists()
    assert (dest / "nested" / "a").read_text() == "trashed"
    assert (dest / "keep").read_text() == "keep"


def test_batch_detects_duplicate_destinations(tmp_path: Path) -> None:
    sources = [tmp_path / "one", tmp_path / "two"]
    for source in sources:
        source.write_text("data")
    dest = tmp_path / "dest"
    with pytest.raises(RestoreConflictError) as caught:
        restore_paths([(str(source), str(dest)) for source in sources], lambda e: False)
    assert caught.value.paths == [str(dest)]
    assert all(source.exists() for source in sources)


def test_partial_merge_can_be_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pytrash._util as util

    source = tmp_path / "trash"
    source.mkdir()
    for name in ("one", "two"):
        (source / name).write_text(name)
    dest = tmp_path / "dest"
    unlink = util.os.unlink
    count = 0

    def interrupt(path: str) -> None:
        nonlocal count
        if str(path).startswith(str(source)):
            count += 1
            if count == 2:
                raise PermissionError("interrupted")
        unlink(path)

    monkeypatch.setattr(util.os, "unlink", interrupt)
    with pytest.raises(PermissionError):
        restore_paths([(str(source), str(dest))], lambda e: False)
    assert len(list(source.iterdir())) == 1
    # A failed source removal leaves both copies; resolving that conflict permits retry.
    remaining = next(source.iterdir())
    (dest / remaining.name).unlink()
    monkeypatch.setattr(util.os, "unlink", unlink)
    restore_paths([(str(source), str(dest))], lambda e: False)
    assert not source.exists()
    assert {p.name for p in dest.iterdir()} == {"one", "two"}


def test_late_file_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.write_text("trashed")
    original_open = builtins.open

    def intercepted_open(file: str, mode: str):  # noqa: ANN202
        if mode == "xb":
            dest.write_text("late arrival")
        return original_open(file, mode)

    monkeypatch.setattr(builtins, "open", intercepted_open)
    with pytest.raises(FileExistsError):
        restore_paths([(str(source), str(dest))], lambda e: False)
    assert source.read_text() == "trashed"
    assert dest.read_text() == "late arrival"
