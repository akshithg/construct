"""Black-box binary execution and model-level simulation."""

from __future__ import annotations

import ctypes
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from construct_demo.fmu import Variable
from construct_demo.primitives import ControllerSketch


def _setpoint(index: int, steps: int, time: float, position: int) -> float:
    del position
    if index < steps // 3:
        plateau = -1.0
    elif index < 2 * steps // 3:
        plateau = 1.6
    else:
        plateau = -1.2
    return 0.9 * math.sin(0.63 * time) + plateau


def _measurement(index: int, steps: int, time: float, position: int) -> float:
    del index, steps, position
    return 0.55 * math.sin(0.41 * time + 0.7) + 0.15 * math.cos(1.3 * time)


def _feedforward(index: int, steps: int, time: float, position: int) -> float:
    del index, steps, position
    return 0.35 * math.cos(0.83 * time) - 0.1 * math.sin(1.7 * time)


def _command(index: int, steps: int, time: float, position: int) -> float:
    del position
    return 1.5 * math.sin(0.7 * time) + (1.0 if index >= steps // 2 else -0.5)


def _position_measurement(index: int, steps: int, time: float, position: int) -> float:
    del index, steps, position
    return 0.4 * math.sin(0.37 * time + 0.2)


def _rate_measurement(index: int, steps: int, time: float, position: int) -> float:
    del index, steps, position
    return 0.25 * math.cos(0.37 * time + 0.2) + 0.1 * math.sin(1.1 * time)


def _schedule(index: int, steps: int, time: float, position: int) -> float:
    del index, steps, position
    return 0.5 + 0.7 * math.sin(1.1 * time - 0.4)


def _fallback_signal(index: int, steps: int, time: float, position: int) -> float:
    del index, steps
    return math.sin((0.31 + position * 0.17) * time + position)


_TRACE_GENERATORS = {
    "setpoint": _setpoint,
    "measurement": _measurement,
    "feedforward": _feedforward,
    "command": _command,
    "positionMeasurement": _position_measurement,
    "rateMeasurement": _rate_measurement,
    "schedule": _schedule,
}


def generate_input_trace(names: Sequence[str], steps: int) -> dict[str, list[float]]:
    """Create deterministic, persistently exciting test inputs."""
    trace: dict[str, list[float]] = {}
    for position, name in enumerate(names):
        generator = _TRACE_GENERATORS.get(name, _fallback_signal)
        trace[name] = [generator(index, steps, index * 0.05, position) for index in range(steps)]
    return trace


def run_binary_oracle(
    binary: Path,
    inputs: Sequence[Variable],
    parameters: Sequence[Variable],
    trace: Mapping[str, Sequence[float]],
    dt: float,
) -> list[float]:
    """Run an extracted controller binary through its FMI-like scalar ABI."""
    library = ctypes.CDLL(str(binary))
    reset = library.fmi_reset
    reset.argtypes = []
    reset.restype = None
    set_real = library.fmi_set_real
    set_real.argtypes = [ctypes.c_int, ctypes.c_double]
    set_real.restype = None
    do_step = library.fmi_do_step
    do_step.argtypes = [ctypes.c_double]
    do_step.restype = None
    get_output = library.fmi_get_output
    get_output.argtypes = []
    get_output.restype = ctypes.c_double

    reset()
    for parameter in parameters:
        set_real(parameter.value_reference, parameter.start)
    steps = len(next(iter(trace.values())))
    outputs: list[float] = []
    for index in range(steps):
        for variable in inputs:
            set_real(variable.value_reference, trace[variable.name][index])
        do_step(dt)
        outputs.append(float(get_output()))
    return outputs


def simulate_sketch(
    sketch: ControllerSketch,
    input_mapping: Sequence[str],
    parameter_mapping: Sequence[str],
    parameter_values: Mapping[str, float],
    trace: Mapping[str, Sequence[float]],
    dt: float,
) -> list[float]:
    """Execute a model-level AST using explicit Euler state updates."""
    parameters = [parameter_values[name] for name in parameter_mapping]
    steps = len(next(iter(trace.values())))
    state = _SimulationState()
    simulator = _SIMULATORS[sketch.kind]
    outputs: list[float] = []
    for index in range(steps):
        values = [trace[name][index] for name in input_mapping]
        outputs.append(simulator(values, parameters, state, dt))
    return outputs


@dataclass
class _SimulationState:
    primary: float = 0.0
    secondary: float = 0.0


class _StepSimulator(Protocol):
    def __call__(
        self, values: list[float], parameters: list[float], state: _SimulationState, dt: float
    ) -> float: ...


def _p_step(
    values: list[float], parameters: list[float], state: _SimulationState, dt: float
) -> float:
    del state, dt
    return parameters[0] * (values[1] - values[0])


def _lowpass_step(
    values: list[float], parameters: list[float], state: _SimulationState, dt: float
) -> float:
    state.primary += dt * (values[0] - state.primary) / parameters[0]
    return state.primary


def _pi_step(
    values: list[float], parameters: list[float], state: _SimulationState, dt: float
) -> float:
    error = values[1] - values[0]
    state.primary += dt * error
    return state.primary * parameters[0] + error * parameters[1]


def _leadlag_step(
    values: list[float], parameters: list[float], state: _SimulationState, dt: float
) -> float:
    state.primary += dt * (values[0] - state.primary) / parameters[0]
    return parameters[2] * (
        state.primary + parameters[1] * (values[0] - state.primary) / parameters[0]
    )


def _rate_limiter_step(
    values: list[float], parameters: list[float], state: _SimulationState, dt: float
) -> float:
    requested = values[0] - state.primary
    applied = min(max(requested, -parameters[0] * dt), parameters[1] * dt)
    state.primary += applied
    return state.primary


def _deadband_pi_step(
    values: list[float], parameters: list[float], state: _SimulationState, dt: float
) -> float:
    raw_error = values[1] - values[0]
    error = 0.0
    if abs(raw_error) > parameters[0]:
        error = raw_error - parameters[0] if raw_error > 0.0 else raw_error + parameters[0]
    state.primary += dt * error
    return parameters[2] * error + parameters[1] * state.primary


def _pid_step(
    values: list[float], parameters: list[float], state: _SimulationState, dt: float
) -> float:
    error = values[1] - values[0]
    state.primary += dt * error
    state.secondary += dt * parameters[0] * (error - state.secondary)
    return (
        parameters[2] * error
        + parameters[3] * state.primary
        + parameters[1] * parameters[0] * (error - state.secondary)
    )


def _cascade_pi_step(
    values: list[float], parameters: list[float], state: _SimulationState, dt: float
) -> float:
    outer_error = values[2] - values[1]
    state.primary += dt * outer_error
    rate_command = parameters[1] * outer_error + parameters[3] * state.primary
    inner_error = rate_command - values[0]
    state.secondary += dt * inner_error
    return parameters[2] * inner_error + parameters[0] * state.secondary


def _gain_scheduled_pi_step(
    values: list[float], parameters: list[float], state: _SimulationState, dt: float
) -> float:
    error = values[2] - values[1]
    low_schedule = values[0] <= parameters[0]
    kp = parameters[2] if low_schedule else parameters[3]
    ki = parameters[4] if low_schedule else parameters[1]
    state.primary += dt * error
    return kp * error + ki * state.primary


def _limpid_step(
    values: list[float], parameters: list[float], state: _SimulationState, dt: float
) -> float:
    error = values[2] - values[1]
    state.primary += dt * error
    state.secondary += dt * parameters[1] * (error - state.secondary)
    raw = (
        parameters[4] * error
        + parameters[5] * state.primary
        + parameters[0] * parameters[1] * (error - state.secondary)
        + values[0]
    )
    return min(max(raw, parameters[3]), parameters[2])


def _antiwindup_pid_step(
    values: list[float], parameters: list[float], state: _SimulationState, dt: float
) -> float:
    error = values[1] - values[0]
    state.secondary += dt * parameters[1] * (error - state.secondary)
    raw = (
        parameters[6] * error
        + state.primary
        + parameters[2] * parameters[1] * (error - state.secondary)
    )
    output = min(max(raw, parameters[5]), parameters[3])
    state.primary += dt * (parameters[4] * error + parameters[0] * (output - raw))
    return output


_SIMULATORS: dict[str, _StepSimulator] = {
    "p": _p_step,
    "lowpass": _lowpass_step,
    "pi": _pi_step,
    "leadlag": _leadlag_step,
    "rate_limiter": _rate_limiter_step,
    "deadband_pi": _deadband_pi_step,
    "pid": _pid_step,
    "cascade_pi": _cascade_pi_step,
    "gain_scheduled_pi": _gain_scheduled_pi_step,
    "limpid": _limpid_step,
    "antiwindup_pid": _antiwindup_pid_step,
}


def mean_squared_error(expected: Sequence[float], actual: Sequence[float]) -> float:
    """Return the mean squared error for equal-length output traces."""
    if len(expected) != len(actual) or not expected:
        raise ValueError("MSE requires non-empty traces of equal length")
    return sum((left - right) ** 2 for left, right in zip(expected, actual, strict=True)) / len(
        expected
    )
