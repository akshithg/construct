"""FMU construction and metadata inspection."""

from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

DEMO_CONTROLLERS = (
    "p",
    "lowpass",
    "pi",
    "leadlag",
    "rate_limiter",
    "deadband_pi",
    "pid",
    "cascade_pi",
    "gain_scheduled_pi",
    "limpid",
    "antiwindup_pid",
)
_MATH_CONTROLLERS = {"rate_limiter", "deadband_pi", "limpid", "antiwindup_pid"}


@dataclass(frozen=True)
class Variable:
    """One scalar variable declared in an FMU model description."""

    name: str
    value_reference: int
    causality: str
    start: float


@dataclass(frozen=True)
class FMUInfo:
    """Relevant metadata and extracted controller binary for an FMU."""

    path: Path
    model_name: str
    model_identifier: str
    variables: tuple[Variable, ...]
    binary_path: Path
    binary_sha256: str

    def by_causality(self, causality: str) -> tuple[Variable, ...]:
        """Return variables with the requested FMI causality."""
        return tuple(variable for variable in self.variables if variable.causality == causality)


def _platform_layout() -> tuple[str, str]:
    system = platform.system()
    machine = platform.machine().lower()
    bits = "64" if machine in {"arm64", "aarch64", "x86_64", "amd64"} else "32"
    if system == "Darwin":
        return f"darwin{bits}", ".dylib"
    if system == "Linux":
        return f"linux{bits}", ".so"
    if system == "Windows":
        return f"win{bits}", ".dll"
    raise RuntimeError(f"unsupported host platform: {system} {machine}")


def build_demo_fmus(repository: Path, output_dir: Path) -> tuple[Path, ...]:
    """Compile the benchmark controllers and package binary-only FMUs."""
    compiler = shutil.which("clang") or shutil.which("gcc")
    if compiler is None:
        raise RuntimeError("building demo FMUs requires clang or gcc on PATH")

    platform_dir, extension = _platform_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    built: list[Path] = []
    for name in DEMO_CONTROLLERS:
        staging = output_dir / f".{name}-staging"
        if staging.exists():
            shutil.rmtree(staging)
        binary_dir = staging / "binaries" / platform_dir
        binary_dir.mkdir(parents=True)
        binary = binary_dir / f"{name}{extension}"
        command = [
            compiler,
            "-O1",
            "-fvisibility=hidden",
            str(repository / "examples/controllers" / f"{name}.c"),
        ]
        if platform.system() == "Darwin":
            command.extend(["-dynamiclib", "-o", str(binary)])
        else:
            command.extend(["-shared", "-fPIC", "-o", str(binary)])
        if name in _MATH_CONTROLLERS and platform.system() != "Darwin":
            command.append("-lm")
        subprocess.run(command, check=True, capture_output=True, text=True)
        strip = shutil.which("strip")
        if strip is not None:
            strip_args = (
                [strip, "-x", str(binary)]
                if platform.system() == "Darwin"
                else [strip, "--strip-unneeded", str(binary)]
            )
            subprocess.run(strip_args, check=True, capture_output=True, text=True)

        shutil.copy2(
            repository / "examples/model_descriptions" / f"{name}.xml",
            staging / "modelDescription.xml",
        )
        fmu_path = output_dir / f"{name}.fmu"
        with zipfile.ZipFile(fmu_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source in sorted(staging.rglob("*")):
                if source.is_file():
                    archive.write(source, source.relative_to(staging))
        shutil.rmtree(staging)
        built.append(fmu_path)
    return tuple(built)


def inspect_fmu(fmu_path: Path, extraction_dir: Path) -> FMUInfo:
    """Safely extract an FMU and parse its FMI 2.0 metadata."""
    extraction_dir.mkdir(parents=True, exist_ok=True)
    root = extraction_dir.resolve()
    with zipfile.ZipFile(fmu_path) as archive:
        for member in archive.infolist():
            destination = (root / member.filename).resolve()
            if root not in destination.parents and destination != root:
                raise ValueError(f"unsafe path in FMU: {member.filename}")
        archive.extractall(root)

    description = root / "modelDescription.xml"
    if not description.is_file():
        raise ValueError("FMU does not contain modelDescription.xml")
    xml_root = ElementTree.parse(description).getroot()
    co_simulation = xml_root.find("CoSimulation")
    if co_simulation is None or not co_simulation.get("modelIdentifier"):
        raise ValueError("FMU does not declare a CoSimulation modelIdentifier")
    model_identifier = str(co_simulation.get("modelIdentifier"))

    variables: list[Variable] = []
    for scalar in xml_root.findall("./ModelVariables/ScalarVariable"):
        real = scalar.find("Real")
        if real is None:
            continue
        variables.append(
            Variable(
                name=str(scalar.get("name")),
                value_reference=int(str(scalar.get("valueReference"))),
                causality=str(scalar.get("causality", "local")),
                start=float(real.get("start", "0")),
            )
        )
    platform_dir, extension = _platform_layout()
    binary = root / "binaries" / platform_dir / f"{model_identifier}{extension}"
    if not binary.is_file():
        raise ValueError(f"FMU controller binary is missing for {platform_dir}: {binary.name}")
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    return FMUInfo(
        path=fmu_path,
        model_name=str(xml_root.get("modelName", model_identifier)),
        model_identifier=model_identifier,
        variables=tuple(variables),
        binary_path=binary,
        binary_sha256=digest,
    )
