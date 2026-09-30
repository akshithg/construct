import pytest

from construct_demo.primitives import ControllerSketch
from construct_demo.simulation import generate_input_trace, mean_squared_error, simulate_sketch
from construct_demo.synthesis import EXACT_MSE, Genome, synthesize_mapping


def test_excitation_crosses_schedule_and_setpoint_regions() -> None:
    trace = generate_input_trace(["schedule", "setpoint"], 160)
    schedule_threshold = 0.5
    assert min(trace["schedule"]) < schedule_threshold < max(trace["schedule"])
    assert min(trace["setpoint"]) < -1.0
    assert max(trace["setpoint"]) > 1.0


@pytest.mark.parametrize(
    ("kind", "inputs", "parameters", "true_inputs", "true_parameters"),
    [
        (
            "p",
            ["measurement", "setpoint"],
            ["Kp"],
            ("measurement", "setpoint"),
            ("Kp",),
        ),
        ("lowpass", ["command"], ["tau"], ("command",), ("tau",)),
        (
            "pi",
            ["measurement", "setpoint"],
            ["Kp", "Ki"],
            ("measurement", "setpoint"),
            ("Ki", "Kp"),
        ),
        (
            "leadlag",
            ["command"],
            ["K", "Tlead", "Tlag"],
            ("command",),
            ("Tlag", "Tlead", "K"),
        ),
        (
            "rate_limiter",
            ["command"],
            ["riseRate", "fallRate"],
            ("command",),
            ("fallRate", "riseRate"),
        ),
        (
            "deadband_pi",
            ["measurement", "setpoint"],
            ["Kp", "deadband", "Ki"],
            ("measurement", "setpoint"),
            ("deadband", "Ki", "Kp"),
        ),
        (
            "pid",
            ["measurement", "setpoint"],
            ["Kd", "N", "Ki", "Kp"],
            ("measurement", "setpoint"),
            ("N", "Kd", "Kp", "Ki"),
        ),
        (
            "cascade_pi",
            ["positionMeasurement", "rateMeasurement", "setpoint"],
            ["outerKp", "innerKi", "outerKi", "innerKp"],
            ("rateMeasurement", "positionMeasurement", "setpoint"),
            ("innerKi", "outerKp", "innerKp", "outerKi"),
        ),
        (
            "gain_scheduled_pi",
            ["measurement", "schedule", "setpoint"],
            ["KpHigh", "KiLow", "threshold", "KiHigh", "KpLow"],
            ("schedule", "measurement", "setpoint"),
            ("threshold", "KiHigh", "KpLow", "KpHigh", "KiLow"),
        ),
        (
            "limpid",
            ["measurement", "feedforward", "setpoint"],
            ["yMax", "Kd", "N", "yMin", "Ki", "Kp"],
            ("feedforward", "measurement", "setpoint"),
            ("Kd", "N", "yMax", "yMin", "Kp", "Ki"),
        ),
        (
            "antiwindup_pid",
            ["measurement", "setpoint"],
            ["yMax", "Kd", "Kaw", "N", "yMin", "Ki", "Kp"],
            ("measurement", "setpoint"),
            ("Kaw", "N", "Kd", "yMax", "Ki", "yMin", "Kp"),
        ),
    ],
)
def test_cbc_synthesis_recovers_exact_mapping(
    kind: str,
    inputs: list[str],
    parameters: list[str],
    true_inputs: tuple[str, ...],
    true_parameters: tuple[str, ...],
) -> None:
    value_table = {
        "Kp": 1.4,
        "Ki": 0.4,
        "Kd": 0.2,
        "N": 3.0,
        "yMin": -8.0,
        "yMax": 8.0,
        "tau": 0.35,
        "K": 1.3,
        "Tlead": 0.12,
        "Tlag": 0.6,
        "riseRate": 2.0,
        "fallRate": 1.2,
        "deadband": 0.15,
        "innerKi": 0.35,
        "outerKp": 1.1,
        "innerKp": 1.8,
        "outerKi": 0.2,
        "threshold": 0.5,
        "KpLow": 1.0,
        "KpHigh": 2.2,
        "KiLow": 0.25,
        "KiHigh": 0.65,
        "Kaw": 0.8,
    }
    state_count = {
        "p": 0,
        "lowpass": 1,
        "pi": 1,
        "leadlag": 1,
        "rate_limiter": 1,
        "deadband_pi": 1,
        "pid": 2,
        "cascade_pi": 2,
        "gain_scheduled_pi": 1,
        "limpid": 2,
        "antiwindup_pid": 2,
    }[kind]
    state_symbols = tuple(f"state{index}" for index in range(state_count))
    sketch = ControllerSketch(
        kind,
        tuple(f"u{index}" for index in range(len(inputs))),
        tuple(f"p{index}" for index in range(len(parameters))),
        state_symbols,
        kind in {"rate_limiter", "limpid", "antiwindup_pid"},
        len(state_symbols) + 1,
        ("+", "-", "*"),
    )
    trace = generate_input_trace(inputs, 100)
    expected = simulate_sketch(sketch, true_inputs, true_parameters, value_table, trace, 0.05)

    def fitness(genome: Genome) -> float:
        actual = simulate_sketch(sketch, genome.inputs, genome.parameters, value_table, trace, 0.05)
        return mean_squared_error(expected, actual)

    result = synthesize_mapping(inputs, parameters, fitness, seed=7)
    assert result.mse <= EXACT_MSE
    assert result.genome == Genome(true_inputs, true_parameters)
