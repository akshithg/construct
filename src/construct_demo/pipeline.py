"""End-to-end CONSTRUCT-inspired recovery pipeline."""

from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TypeAlias

from construct_demo.decompiler import decompile_controller
from construct_demo.fmu import FMUInfo, inspect_fmu
from construct_demo.modelica import render_modelica
from construct_demo.primitives import ControllerSketch, isolate_primitives
from construct_demo.simulation import (
    generate_input_trace,
    mean_squared_error,
    run_binary_oracle,
    simulate_sketch,
)
from construct_demo.synthesis import Genome, SynthesisResult, synthesize_mapping

MetricValue: TypeAlias = int | float


@dataclass(frozen=True)
class PipelineResult:
    """Paths and metrics produced by one reconstruction run."""

    model_name: str
    controller_kind: str
    mse: float
    generations_run: int
    evaluations: int
    input_count: int
    parameter_count: int
    state_count: int
    search_space: int
    decompiled_assignments: int
    decompilation_seconds: float
    synthesis_seconds: float
    total_seconds: float
    excitation: dict[str, MetricValue]
    coverage_summary: str
    input_mapping: tuple[str, ...]
    parameter_mapping: tuple[str, ...]
    modelica_path: Path
    report_path: Path


@dataclass(frozen=True)
class PipelineConfig:
    """Numerical and search settings for one reconstruction run."""

    population_size: int = 400
    generations: int = 10
    seed: int = 7
    steps: int = 160
    dt: float = 0.05


@dataclass(frozen=True)
class _ReportData:
    final_mse: float
    decompiled_path: Path
    modelica_path: Path
    steps: int
    dt: float
    search_space: int
    decompilation_seconds: float
    synthesis_seconds: float
    total_seconds: float
    excitation: dict[str, MetricValue]


_MAX_VALIDATION_MSE = 1e-12
_COMPARISON_TOLERANCE = 1e-12


def _excitation_metrics(
    kind: str,
    trace: dict[str, list[float]],
    outputs: list[float],
    parameters: dict[str, float],
    dt: float,
) -> dict[str, MetricValue]:
    metrics: dict[str, MetricValue] = {
        "trace_samples": len(outputs),
        "output_min": min(outputs),
        "output_max": max(outputs),
    }
    if kind in {"limpid", "antiwindup_pid"}:
        limits = (parameters["yMin"], parameters["yMax"])
        metrics["saturated_samples"] = sum(
            any(math.isclose(value, limit, abs_tol=_COMPARISON_TOLERANCE) for limit in limits)
            for value in outputs
        )
    elif kind == "gain_scheduled_pi":
        threshold = parameters["threshold"]
        low_samples = sum(value <= threshold for value in trace["schedule"])
        metrics["low_schedule_samples"] = low_samples
        metrics["high_schedule_samples"] = len(outputs) - low_samples
    elif kind == "deadband_pi":
        metrics["inside_deadband_samples"] = sum(
            abs(setpoint - measurement) <= parameters["deadband"]
            for setpoint, measurement in zip(trace["setpoint"], trace["measurement"], strict=True)
        )
    elif kind == "rate_limiter":
        previous = 0.0
        limited_samples = 0
        for command, output in zip(trace["command"], outputs, strict=True):
            requested = command - previous
            if requested < -parameters["fallRate"] * dt or requested > parameters["riseRate"] * dt:
                limited_samples += 1
            previous = output
        metrics["rate_limited_samples"] = limited_samples
    return metrics


def _coverage_summary(kind: str, metrics: dict[str, MetricValue]) -> str:
    total = metrics["trace_samples"]
    if kind in {"limpid", "antiwindup_pid"}:
        return f"saturated={metrics['saturated_samples']}/{total}"
    if kind == "gain_scheduled_pi":
        return f"low/high={metrics['low_schedule_samples']}/{metrics['high_schedule_samples']}"
    if kind == "deadband_pi":
        return f"inside_deadband={metrics['inside_deadband_samples']}/{total}"
    if kind == "rate_limiter":
        return f"rate_limited={metrics['rate_limited_samples']}/{total}"
    return "linear"


def _write_trace_csv(
    path: Path,
    trace: dict[str, list[float]],
    binary_output: list[float],
    recovered_output: list[float],
    dt: float,
) -> None:
    names = list(trace)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time", *names, "binary_output", "recovered_output", "squared_error"])
        for index, (expected, actual) in enumerate(
            zip(binary_output, recovered_output, strict=True)
        ):
            writer.writerow(
                [
                    index * dt,
                    *(trace[name][index] for name in names),
                    expected,
                    actual,
                    (expected - actual) ** 2,
                ]
            )


def _polyline(values: list[float], width: int, height: int, top: float, bottom: float) -> str:
    span = top - bottom or 1.0
    return " ".join(
        f"{40 + index * (width - 60) / max(1, len(values) - 1):.2f},"
        f"{20 + (top - value) * (height - 50) / span:.2f}"
        for index, value in enumerate(values)
    )


def _write_comparison_svg(path: Path, expected: list[float], actual: list[float]) -> None:
    width, height = 920, 360
    top = max(expected + actual)
    bottom = min(expected + actual)
    expected_points = _polyline(expected, width, height, top, bottom)
    actual_points = _polyline(actual, width, height, top, bottom)
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '  <rect width="100%" height="100%" fill="#fbfbfd"/>',
        '  <text x="40" y="18" font-family="sans-serif" font-size="14">'
        "Binary oracle vs recovered model</text>",
        '  <line x1="40" y1="20" x2="40" y2="330" stroke="#aaa"/>',
        '  <line x1="40" y1="330" x2="900" y2="330" stroke="#aaa"/>',
        f'  <polyline fill="none" stroke="#2563eb" stroke-width="2" points="{expected_points}"/>',
        f'  <polyline fill="none" stroke="#f97316" stroke-width="1.5" '
        f'stroke-dasharray="5 4" points="{actual_points}"/>',
        '  <text x="650" y="18" font-family="sans-serif" font-size="12" '
        'fill="#2563eb">binary</text>',
        '  <text x="715" y="18" font-family="sans-serif" font-size="12" '
        'fill="#f97316">recovered</text>',
        "</svg>",
        "",
    ]
    svg = "\n".join(svg_lines)
    path.write_text(svg, encoding="utf-8")


def _validate_shape(info: FMUInfo, sketch: ControllerSketch) -> None:
    input_count = len(info.by_causality("input"))
    parameter_count = len(info.by_causality("parameter"))
    if input_count != len(sketch.input_symbols) or parameter_count != len(sketch.parameter_symbols):
        raise ValueError(
            "decompiled controller shape disagrees with FMU metadata: "
            f"sketch has {len(sketch.input_symbols)} inputs/{len(sketch.parameter_symbols)} "
            f"parameters, metadata has {input_count}/{parameter_count}"
        )


def run_pipeline(
    fmu_path: Path,
    output_dir: Path,
    repository: Path,
    config: PipelineConfig | None = None,
) -> PipelineResult:
    """Recover, synthesize, render, and verify one controller FMU."""
    started_at = time.perf_counter()
    settings = config or PipelineConfig()
    output_dir.mkdir(parents=True, exist_ok=True)
    extraction_dir = output_dir / "extracted_fmu"
    info = inspect_fmu(fmu_path, extraction_dir)
    decompilation_started_at = time.perf_counter()
    decompiled_path = decompile_controller(
        info.binary_path, output_dir / "decompilation", repository
    )
    decompilation_seconds = time.perf_counter() - decompilation_started_at
    decompiled_c = decompiled_path.read_text(encoding="utf-8")
    sketch = isolate_primitives(
        decompiled_c,
        len(info.by_causality("input")),
        len(info.by_causality("parameter")),
    )
    _validate_shape(info, sketch)

    inputs = info.by_causality("input")
    parameters = info.by_causality("parameter")
    output_variables = info.by_causality("output")
    if len(output_variables) != 1:
        raise ValueError(f"demo expects exactly one output, found {len(output_variables)}")
    trace = generate_input_trace([variable.name for variable in inputs], settings.steps)
    binary_output = run_binary_oracle(info.binary_path, inputs, parameters, trace, settings.dt)
    parameter_values = {variable.name: variable.start for variable in parameters}

    def fitness(genome: Genome) -> float:
        candidate = simulate_sketch(
            sketch,
            genome.inputs,
            genome.parameters,
            parameter_values,
            trace,
            settings.dt,
        )
        return mean_squared_error(binary_output, candidate)

    synthesis_started_at = time.perf_counter()
    synthesis = synthesize_mapping(
        [variable.name for variable in inputs],
        [variable.name for variable in parameters],
        fitness,
        population_size=settings.population_size,
        generations=settings.generations,
        seed=settings.seed,
    )
    synthesis_seconds = time.perf_counter() - synthesis_started_at
    recovered_output = simulate_sketch(
        sketch,
        synthesis.genome.inputs,
        synthesis.genome.parameters,
        parameter_values,
        trace,
        settings.dt,
    )
    final_mse = mean_squared_error(binary_output, recovered_output)
    if final_mse > _MAX_VALIDATION_MSE:
        raise RuntimeError(
            f"synthesis did not recover an equivalent model: final MSE is {final_mse:.6g}"
        )

    output_name = output_variables[0].name
    excitation = _excitation_metrics(
        sketch.kind, trace, binary_output, parameter_values, settings.dt
    )
    modelica_path = output_dir / "recovered.mo"
    modelica_path.write_text(
        render_modelica(
            info.model_name,
            output_name,
            sketch,
            synthesis.genome,
            parameter_values,
        ),
        encoding="utf-8",
    )
    _write_trace_csv(
        output_dir / "validation_trace.csv",
        trace,
        binary_output,
        recovered_output,
        settings.dt,
    )
    _write_comparison_svg(output_dir / "comparison.svg", binary_output, recovered_output)
    report_path = output_dir / "report.json"
    search_space = math.factorial(len(inputs)) * math.factorial(len(parameters))
    total_seconds = time.perf_counter() - started_at
    report = _make_report(
        info,
        sketch,
        synthesis,
        _ReportData(
            final_mse,
            decompiled_path,
            modelica_path,
            settings.steps,
            settings.dt,
            search_space,
            decompilation_seconds,
            synthesis_seconds,
            total_seconds,
            excitation,
        ),
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return PipelineResult(
        model_name=info.model_name,
        controller_kind=sketch.kind,
        mse=final_mse,
        generations_run=len(synthesis.history),
        evaluations=synthesis.evaluations,
        input_count=len(inputs),
        parameter_count=len(parameters),
        state_count=len(sketch.state_symbols),
        search_space=search_space,
        decompiled_assignments=sketch.decompiled_assignments,
        decompilation_seconds=decompilation_seconds,
        synthesis_seconds=synthesis_seconds,
        total_seconds=total_seconds,
        excitation=excitation,
        coverage_summary=_coverage_summary(sketch.kind, excitation),
        input_mapping=synthesis.genome.inputs,
        parameter_mapping=synthesis.genome.parameters,
        modelica_path=modelica_path,
        report_path=report_path,
    )


def _make_report(
    info: FMUInfo,
    sketch: ControllerSketch,
    synthesis: SynthesisResult,
    run: _ReportData,
) -> dict[str, object]:
    return {
        "source_fmu": str(info.path),
        "model_name": info.model_name,
        "binary_sha256": info.binary_sha256,
        "variables": [asdict(variable) for variable in info.variables],
        "static_analysis": {
            "controller_kind": sketch.kind,
            "operators": sketch.operators,
            "state_symbols": sketch.state_symbols,
            "has_saturation": sketch.has_saturation,
            "decompiled_assignments": sketch.decompiled_assignments,
            "decompiled_c": str(run.decompiled_path),
        },
        "synthesis": {
            "method": "correct-by-construction genetic permutation search",
            "input_mapping": dict(zip(sketch.input_symbols, synthesis.genome.inputs, strict=True)),
            "parameter_mapping": dict(
                zip(sketch.parameter_symbols, synthesis.genome.parameters, strict=True)
            ),
            "mse_by_generation": synthesis.history,
            "evaluations": synthesis.evaluations,
            "search_space": run.search_space,
        },
        "validation": {"steps": run.steps, "dt": run.dt, "final_mse": run.final_mse},
        "excitation": run.excitation,
        "timing_seconds": {
            "decompilation": run.decompilation_seconds,
            "synthesis": run.synthesis_seconds,
            "total": run.total_seconds,
        },
        "modelica_model": str(run.modelica_path),
    }
