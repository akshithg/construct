"""Modelica rendering for recovered controller models."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from construct_demo.primitives import ControllerSketch
from construct_demo.synthesis import Genome


def _p_equations(output: str, inputs: Sequence[str], parameters: Sequence[str]) -> list[str]:
    measurement, setpoint = inputs
    (kp,) = parameters
    return [f"  error = {setpoint} - {measurement};", f"  {output} = {kp} * error;"]


def _lowpass_equations(output: str, inputs: Sequence[str], parameters: Sequence[str]) -> list[str]:
    (command,) = inputs
    (tau,) = parameters
    return [
        f"  der(filteredState) = ({command} - filteredState) / {tau};",
        f"  {output} = filteredState;",
    ]


def _pi_equations(output: str, inputs: Sequence[str], parameters: Sequence[str]) -> list[str]:
    measurement, setpoint = inputs
    ki, kp = parameters
    return [
        f"  error = {setpoint} - {measurement};",
        "  der(integral) = error;",
        f"  {output} = {kp} * error + {ki} * integral;",
    ]


def _leadlag_equations(output: str, inputs: Sequence[str], parameters: Sequence[str]) -> list[str]:
    (command,) = inputs
    t_lag, t_lead, gain = parameters
    return [
        f"  der(lagState) = ({command} - lagState) / {t_lag};",
        f"  {output} = {gain} * (lagState + {t_lead} / {t_lag} * ({command} - lagState));",
    ]


def _rate_limiter_equations(
    output: str, inputs: Sequence[str], parameters: Sequence[str]
) -> list[str]:
    (command,) = inputs
    fall_rate, rise_rate = parameters
    return [
        f"  der(limitedState) = min(max({command} - limitedState, -{fall_rate}), {rise_rate});",
        f"  {output} = limitedState;",
    ]


def _deadband_pi_equations(
    output: str, inputs: Sequence[str], parameters: Sequence[str]
) -> list[str]:
    measurement, setpoint = inputs
    deadband, ki, kp = parameters
    return [
        f"  rawError = {setpoint} - {measurement};",
        f"  effectiveError = if abs(rawError) <= {deadband} then 0 else "
        f"if rawError > 0 then rawError - {deadband} else rawError + {deadband};",
        "  der(integral) = effectiveError;",
        f"  {output} = {kp} * effectiveError + {ki} * integral;",
    ]


def _pid_equations(output: str, inputs: Sequence[str], parameters: Sequence[str]) -> list[str]:
    measurement, setpoint = inputs
    n_gain, kd, kp, ki = parameters
    return [
        f"  error = {setpoint} - {measurement};",
        "  der(integral) = error;",
        f"  der(derivativeFilter) = {n_gain} * (error - derivativeFilter);",
        f"  {output} = {kp} * error + {ki} * integral + {kd} * {n_gain} * "
        "(error - derivativeFilter);",
    ]


def _cascade_pi_equations(
    output: str, inputs: Sequence[str], parameters: Sequence[str]
) -> list[str]:
    rate_measurement, position_measurement, setpoint = inputs
    inner_ki, outer_kp, inner_kp, outer_ki = parameters
    return [
        f"  outerError = {setpoint} - {position_measurement};",
        "  der(outerIntegral) = outerError;",
        f"  rateCommand = {outer_kp} * outerError + {outer_ki} * outerIntegral;",
        f"  innerError = rateCommand - {rate_measurement};",
        "  der(innerIntegral) = innerError;",
        f"  {output} = {inner_kp} * innerError + {inner_ki} * innerIntegral;",
    ]


def _gain_scheduled_pi_equations(
    output: str, inputs: Sequence[str], parameters: Sequence[str]
) -> list[str]:
    schedule, measurement, setpoint = inputs
    threshold, ki_high, kp_low, kp_high, ki_low = parameters
    return [
        f"  error = {setpoint} - {measurement};",
        f"  scheduledKp = if {schedule} <= {threshold} then {kp_low} else {kp_high};",
        f"  scheduledKi = if {schedule} <= {threshold} then {ki_low} else {ki_high};",
        "  der(integral) = error;",
        f"  {output} = scheduledKp * error + scheduledKi * integral;",
    ]


def _limpid_equations(output: str, inputs: Sequence[str], parameters: Sequence[str]) -> list[str]:
    feedforward, measurement, setpoint = inputs
    kd, n_gain, y_max, y_min, kp, ki = parameters
    return [
        f"  error = {setpoint} - {measurement};",
        "  der(integral) = error;",
        f"  der(derivativeFilter) = {n_gain} * (error - derivativeFilter);",
        f"  rawOutput = {kp} * error + {ki} * integral + {kd} * {n_gain} * "
        f"(error - derivativeFilter) + {feedforward};",
        f"  {output} = min(max(rawOutput, {y_min}), {y_max});",
    ]


def _antiwindup_pid_equations(
    output: str, inputs: Sequence[str], parameters: Sequence[str]
) -> list[str]:
    measurement, setpoint = inputs
    kaw, n_gain, kd, y_max, ki, y_min, kp = parameters
    return [
        f"  error = {setpoint} - {measurement};",
        f"  der(derivativeFilter) = {n_gain} * (error - derivativeFilter);",
        f"  rawOutput = {kp} * error + integralTerm + {kd} * {n_gain} * "
        "(error - derivativeFilter);",
        f"  {output} = min(max(rawOutput, {y_min}), {y_max});",
        f"  der(integralTerm) = {ki} * error + {kaw} * ({output} - rawOutput);",
    ]


_EQUATION_RENDERERS: dict[str, Callable[[str, Sequence[str], Sequence[str]], list[str]]] = {
    "p": _p_equations,
    "lowpass": _lowpass_equations,
    "pi": _pi_equations,
    "leadlag": _leadlag_equations,
    "rate_limiter": _rate_limiter_equations,
    "deadband_pi": _deadband_pi_equations,
    "pid": _pid_equations,
    "cascade_pi": _cascade_pi_equations,
    "gain_scheduled_pi": _gain_scheduled_pi_equations,
    "limpid": _limpid_equations,
    "antiwindup_pid": _antiwindup_pid_equations,
}

_LOCALS = {
    "p": ("Real error;",),
    "lowpass": ("Real filteredState(start = 0);",),
    "pi": ("Real error;", "Real integral(start = 0);"),
    "leadlag": ("Real lagState(start = 0);",),
    "rate_limiter": ("Real limitedState(start = 0);",),
    "deadband_pi": (
        "Real rawError;",
        "Real effectiveError;",
        "Real integral(start = 0);",
    ),
    "pid": ("Real error;", "Real integral(start = 0);", "Real derivativeFilter(start = 0);"),
    "cascade_pi": (
        "Real outerError;",
        "Real outerIntegral(start = 0);",
        "Real rateCommand;",
        "Real innerError;",
        "Real innerIntegral(start = 0);",
    ),
    "gain_scheduled_pi": (
        "Real error;",
        "Real integral(start = 0);",
        "Real scheduledKp;",
        "Real scheduledKi;",
    ),
    "limpid": (
        "Real error;",
        "Real integral(start = 0);",
        "Real derivativeFilter(start = 0);",
        "Real rawOutput;",
    ),
    "antiwindup_pid": (
        "Real error;",
        "Real integralTerm(start = 0);",
        "Real derivativeFilter(start = 0);",
        "Real rawOutput;",
    ),
}


def render_modelica(
    model_name: str,
    output_name: str,
    sketch: ControllerSketch,
    genome: Genome,
    parameter_values: Mapping[str, float],
) -> str:
    """Render a readable continuous-time Modelica representation."""
    lines = [f"model Recovered{model_name}"]
    lines.extend(f"  input Real {name};" for name in genome.inputs)
    lines.append(f"  output Real {output_name};")
    lines.extend(
        f"  parameter Real {name} = {parameter_values[name]:.12g};" for name in genome.parameters
    )
    lines.extend(f"  {declaration}" for declaration in _LOCALS[sketch.kind])
    lines.append("equation")
    lines.extend(_EQUATION_RENDERERS[sketch.kind](output_name, genome.inputs, genome.parameters))
    lines.extend([f"end Recovered{model_name};", ""])
    return "\n".join(lines)
