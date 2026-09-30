# CONSTRUCT demo

This project turns a compiled controller into a readable mathematical model, then checks that the
recovered model behaves like the original binary.

The workflow follows the approach described in the paper
[*CONSTRUCT: A Program Synthesis Approach for Reconstructing Control Algorithms from Embedded
System Binaries in Cyber-Physical Systems*](2308.00250v1.pdf).

```text
FMU with a controller binary
          ↓
    Ghidra decompilation
          ↓
   Mathematical sketch
          ↓
 Search for variable names
          ↓
 Modelica model + validation report
```

You can run the complete experiment locally. It builds eleven example controllers, removes their
source code from the input packages, reconstructs them from the binaries, and reports how well the
recovered models match.

## Quick start

You need Python 3.11 or newer, [`uv`](https://docs.astral.sh/uv/), Clang or GCC, Java, and Ghidra.
On macOS, Ghidra can be installed with:

```bash
brew install --cask ghidra
```

Install the Python environment and run every example:

```bash
uv sync --extra dev
uv run construct-demo demo --output-dir artifacts
```

The full benchmark usually takes under a minute on a modern laptop. Most of that time is spent in
Ghidra.

When it finishes, start with these files:

- `artifacts/benchmark.md` contains the readable results table.
- `artifacts/summary.json` contains detailed results for all controllers.
- `artifacts/runs/<controller>/recovered.mo` is the recovered Modelica model.
- `artifacts/runs/<controller>/comparison.svg` plots the binary and recovered outputs together.

> Only load FMUs that you trust. This demo executes the shared library inside each FMU with your
> user account's permissions.

## What happens during a run

An FMU is a ZIP archive used to exchange simulation models. Each example FMU contains two things:

- A native controller library, such as a `.dylib` or `.so` file.
- `modelDescription.xml`, which lists the controller's inputs, outputs, and parameters.

The reconstruction follows five steps:

1. Read the variable names and types from `modelDescription.xml`.
2. Extract the controller library and decompile its step function with Ghidra.
3. Recognize control patterns such as integration, derivative filtering, limits, and deadbands.
4. Search for the mapping between unnamed binary slots and the names found in the FMU metadata.
5. Generate Modelica and run the binary and recovered model on the same input signals.

The search only creates valid mappings. An input can map only to another input, parameters cannot
be duplicated, and every name is used exactly once. These constraints follow the paper's
"correct by construction" idea.

A reconstruction passes when the mean squared difference between the two output traces is at most
`1e-12`.

## Included examples

The examples progress from small linear blocks to controllers with nested loops and nonlinear
protection.

| Example | What it represents |
|---|---|
| Proportional | Basic thermal, pressure, or valve regulation |
| First-order low-pass | Sensor or command filtering |
| PI | Motor speed and process control |
| Lead-lag | Frequency-domain loop shaping |
| Rate limiter | Actuator slew-rate protection |
| Deadband PI | Backlash or insensitive-zone compensation |
| PID with filtered derivative | Servo and motion control |
| Cascade PI | A position outer loop with a rate inner loop |
| Gain-scheduled PI | Gains that change with speed or operating point |
| Limited PID with feedforward | Saturated control with a known load term |
| Anti-windup PID | Saturated control with back-calculation recovery |

The test signals deliberately exercise both sides of each nonlinear behavior. For example, the
gain-scheduled controller visits both schedules, and the limited controllers contain both saturated
and unsaturated intervals.

## Current results

With the default settings on an Apple Silicon macOS host, all eleven examples passed.

- Final mean squared error ranged from zero to `2.60e-31`, which is floating-point roundoff for
  these traces.
- The search space ranged from 1 valid mapping for the low-pass filter to 10,080 for the
  anti-windup PID.
- The simple cases converged in the first generation. Gain-scheduled PI took two generations,
  limited PID took three, and anti-windup PID took four.
- Ghidra took about 3.9 to 4.0 seconds per binary. The mapping search took less than 0.09 seconds in
  every case.

The nonlinear coverage was:

| Behavior | Samples exercised |
|---|---:|
| Rate limiting | 13 of 160 |
| Inside the deadband | 23 of 160 |
| Low/high gain schedule | 65 / 95 |
| Limited PID saturation | 28 of 160 |
| Anti-windup PID saturation | 47 of 160 |

Exact timing depends on the machine. See `artifacts/benchmark.md` for the complete result and
`artifacts/benchmark.csv` for the same data in a machine-readable format.

## Understanding the output

Each controller gets its own directory under `artifacts/runs/`:

```text
artifacts/runs/pid/
├── decompilation/
│   ├── controller_decompiled.c
│   └── ghidra logs
├── extracted_fmu/
├── recovered.mo
├── report.json
├── validation_trace.csv
└── comparison.svg
```

| File | Why it is useful |
|---|---|
| `controller_decompiled.c` | Shows what the static-analysis stage received from Ghidra |
| `recovered.mo` | Contains the final mathematical model in Modelica |
| `report.json` | Records the binary hash, recovered mapping, fitness history, timing, and coverage |
| `validation_trace.csv` | Contains every test input and both output traces |
| `comparison.svg` | Makes output differences visible at a glance |

The top-level `benchmark.md`, `benchmark.csv`, and `summary.json` combine the individual results.

## Running one example

Build the binary-only FMUs without reconstructing them:

```bash
uv run construct-demo build --output-dir artifacts/fmus
```

Then reconstruct one controller:

```bash
uv run construct-demo run artifacts/fmus/pid.fmu --output-dir artifacts/runs/pid
```

You can change the genetic search settings with `--population`, `--generations`, and `--seed`.
The defaults are a population of 400, a limit of 10 generations, and seed 7. The population and
generation limit match the settings reported in the paper.

## Prerequisites in detail

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/)
- Clang or GCC
- `strip`
- Ghidra with `analyzeHeadless` available on `PATH`, in a common Homebrew location, or under
  `GHIDRA_HOME`
- A Java version supported by the installed Ghidra release

The demo builds native binaries for macOS and Linux. An FMU built on one operating system cannot be
used directly on the other; rerun the build command on the target system.

## Paper context

The paper describes the four-stage approach and reports results for PI, PID, and limited PID
controllers. This benchmark includes those three controller families and eight additional examples.

## Scope and limitations

- The static analyzer recognizes the eleven known topologies in this repository. It is not a
  general C-to-Modelica translator.
- The example FMUs use a small FMI-like controller interface instead of the complete FMI 2.0
  runtime API.
- Validation uses 160 designed input samples. It provides strong evidence for those traces, not a
  proof of equivalence for every possible input.
- The benchmark uses one deterministic seed, so it is not a statistical study of genetic search
  variance.
- Generated Modelica has not been compiled with OpenModelica in the current environment. Numerical
  validation uses the same explicit-Euler update order as the binaries.

Supporting arbitrary industrial FMUs would require a complete FMI loader, broader data-flow and
pointer analysis, recovery across helper functions, a larger Modelica grammar, and sandboxed native
execution.

## Development checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest -q
```

The tests cover FMU path safety, compiler-specific decompiler patterns, input-signal excitation,
and exact mapping recovery for all eleven controller families. The full `demo` command additionally
checks native compilation, Ghidra, artifact generation, and numerical equivalence.

## Repository map

- `src/construct_demo/` contains the reconstruction pipeline and command-line interface.
- `examples/controllers/` contains source used only to build the binary fixtures.
- `examples/model_descriptions/` contains the FMI metadata for those fixtures.
- `tools/ghidra/` contains the Ghidra export script.
- `tests/` contains the focused automated tests.
- `2308.00250v1.pdf` is the source paper.
