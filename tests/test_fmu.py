import zipfile
from pathlib import Path

import pytest

from construct_demo.fmu import inspect_fmu


def test_rejects_zip_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.fmu"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escaped", "bad")
    with pytest.raises(ValueError, match="unsafe path"):
        inspect_fmu(archive_path, tmp_path / "extract")
