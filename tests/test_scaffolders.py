"""Scaffolders produce valid manifests and refuse to overwrite.

Runs the real scripts against a throwaway copy of the repo skeleton so the
working tree is never modified.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from cdsim_common.paths import repo_root

ROOT = repo_root()
assert ROOT is not None


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    dst = tmp_path / "repo"
    dst.mkdir()
    shutil.copy(ROOT / "CLAUDE.md", dst / "CLAUDE.md")
    shutil.copytree(ROOT / "schemas", dst / "schemas", ignore=shutil.ignore_patterns("gen"))
    shutil.copytree(ROOT / "platforms" / "_template", dst / "platforms" / "_template")
    shutil.copytree(ROOT / "scripts", dst / "scripts", ignore=shutil.ignore_patterns("ue5"))
    (dst / "terrain" / "areas").mkdir(parents=True)
    return dst


def _run(repo: Path, script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / script), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_new_platform(repo_copy: Path) -> None:
    r = _run(repo_copy, "new_platform.py", "test_rover_01")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (repo_copy / "platforms" / "test_rover_01" / "platform.yaml").is_file()
    plugin = repo_copy / "sim" / "Plugins" / "CDSimPlatform_test_rover_01"
    assert (plugin / "CDSimPlatform_test_rover_01.uplugin").is_file()
    assert _run(repo_copy, "new_platform.py", "test_rover_01").returncode == 1
    assert _run(repo_copy, "new_platform.py", "Bad-Id").returncode == 2


def test_new_area(repo_copy: Path) -> None:
    r = _run(repo_copy, "new_area.py", "test_area_01", "--lat", "17.5", "--lon", "78.4")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (repo_copy / "terrain" / "areas" / "test_area_01" / "area.yaml").is_file()
    assert _run(repo_copy, "new_area.py", "test_area_01").returncode == 1
