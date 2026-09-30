"""Command-line entry point for the CONSTRUCT demo."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from construct_demo.fmu import build_demo_fmus
from construct_demo.pipeline import PipelineConfig, PipelineResult, run_pipeline


def _repository() -> Path:
    return Path(__file__).resolve().parents[2]


def _result_dict(result: PipelineResult) -> dict[str, object]:
    return {
        "model_name": result.model_name,
        "controller_kind": result.controller_kind,
        "mse": result.mse,
        "generations_run": result.generations_run,
        "evaluations": result.evaluations,
        "input_count": result.input_count,
        "parameter_count": result.parameter_count,
        "state_count": result.state_count,
        "search_space": result.search_space,
        "decompiled_assignments": result.decompiled_assignments,
        "decompilation_seconds": result.decompilation_seconds,
        "synthesis_seconds": result.synthesis_seconds,
        "total_seconds": result.total_seconds,
        "excitation": result.excitation,
        "coverage": result.coverage_summary,
        "input_mapping": result.input_mapping,
        "parameter_mapping": result.parameter_mapping,
        "modelica_path": str(result.modelica_path),
        "report_path": str(result.report_path),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="construct-demo",
        description="Recover Modelica controller models from binary-only demo FMUs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="compile and package the demo FMUs")
    build.add_argument("--output-dir", type=Path, default=Path("artifacts/fmus"))

    run = subparsers.add_parser("run", help="recover one FMU")
    run.add_argument("fmu", type=Path)
    run.add_argument("--output-dir", type=Path, default=Path("artifacts/run"))
    _add_search_options(run)

    demo = subparsers.add_parser("demo", help="build and benchmark all controllers")
    demo.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    _add_search_options(demo)
    return parser


def _add_search_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--population", type=int, default=400)
    parser.add_argument("--generations", type=int, default=10)
    parser.add_argument("--seed", type=int, default=7)


def _config(args: argparse.Namespace) -> PipelineConfig:
    return PipelineConfig(args.population, args.generations, args.seed)


def _write_benchmark(results: list[PipelineResult], output_dir: Path) -> None:
    columns = [
        "controller_kind",
        "input_count",
        "parameter_count",
        "state_count",
        "search_space",
        "decompiled_assignments",
        "generations_run",
        "evaluations",
        "mse",
        "decompilation_seconds",
        "synthesis_seconds",
        "total_seconds",
        "coverage",
    ]
    with (output_dir / "benchmark.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for result in results:
            values = _result_dict(result)
            writer.writerow({column: values[column] for column in columns})

    lines = [
        "# Controller reconstruction benchmark",
        "",
        "All cases used the same population, generation limit, validation trace length, and seed.",
        "A run counts as successful only when its final binary-to-model MSE is at most `1e-12`.",
        "",
        "| Controller | Inputs | Parameters | States | Search space | Generations | "
        "Evaluations | MSE | Coverage | Total seconds |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for result in results:
        lines.append(
            f"| {result.controller_kind} | {result.input_count} | {result.parameter_count} | "
            f"{result.state_count} | {result.search_space} | {result.generations_run} | "
            f"{result.evaluations} | {result.mse:.3e} | {result.coverage_summary} | "
            f"{result.total_seconds:.3f} |"
        )
    lines.extend(
        [
            "",
            "Search space is `inputs! x parameters!` after causality constraints. Timing is local "
            "wall-clock time and includes FMU inspection, Ghidra, synthesis, and artifact output.",
            "",
        ]
    )
    (output_dir / "benchmark.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Run the requested build or reconstruction command."""
    args = _parser().parse_args(argv)
    repository = _repository()
    if args.command == "build":
        paths = build_demo_fmus(repository, args.output_dir.resolve())
        print("\n".join(str(path) for path in paths))
        return 0
    if args.command == "run":
        result = run_pipeline(
            args.fmu.resolve(),
            args.output_dir.resolve(),
            repository,
            _config(args),
        )
        print(json.dumps(_result_dict(result), indent=2))
        return 0

    fmu_dir = args.output_dir.resolve() / "fmus"
    paths = build_demo_fmus(repository, fmu_dir)
    results = [
        run_pipeline(
            path,
            args.output_dir.resolve() / "runs" / path.stem,
            repository,
            _config(args),
        )
        for path in paths
    ]
    summary = {"runs": [_result_dict(result) for result in results]}
    summary_path = args.output_dir.resolve() / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_benchmark(results, args.output_dir.resolve())
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
