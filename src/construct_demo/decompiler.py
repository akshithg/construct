"""Headless Ghidra integration for controller decompilation."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def find_analyze_headless() -> Path:
    """Locate Ghidra's analyzeHeadless launcher."""
    configured = os.environ.get("GHIDRA_HOME")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured) / "support" / "analyzeHeadless")
    direct = shutil.which("analyzeHeadless")
    if direct:
        candidates.append(Path(direct))
    candidates.extend(
        [
            Path("/opt/homebrew/opt/ghidra/libexec/support/analyzeHeadless"),
            Path("/usr/local/opt/ghidra/libexec/support/analyzeHeadless"),
            Path("/Applications/ghidra/support/analyzeHeadless"),
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("Ghidra analyzeHeadless was not found; install Ghidra or set GHIDRA_HOME")


def decompile_controller(binary: Path, output_dir: Path, repository: Path) -> Path:
    """Decompile the exported controller step function with Ghidra."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "controller_decompiled.c"
    log_file = output_dir / "ghidra.log"
    launcher = find_analyze_headless()
    script_dir = repository / "tools" / "ghidra"
    with tempfile.TemporaryDirectory(prefix="construct-ghidra-") as project_dir:
        command = [
            str(launcher),
            project_dir,
            "construct",
            "-import",
            str(binary),
            "-scriptPath",
            str(script_dir),
            "-postScript",
            "ExportController.java",
            str(output_file),
            "-analysisTimeoutPerFile",
            "120",
            "-deleteProject",
            "-log",
            str(log_file),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    (output_dir / "ghidra.stdout.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode != 0 or not output_file.is_file():
        raise RuntimeError(
            f"Ghidra failed for {binary.name}; see {output_dir / 'ghidra.stdout.log'}"
        )
    return output_file
