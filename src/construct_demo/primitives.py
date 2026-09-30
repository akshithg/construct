"""Rule-based mathematical primitive isolation from decompiled C."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ControllerSketch:
    """Model-level AST sketch recovered from controller arithmetic."""

    kind: str
    input_symbols: tuple[str, ...]
    parameter_symbols: tuple[str, ...]
    state_symbols: tuple[str, ...]
    has_saturation: bool
    decompiled_assignments: int
    operators: tuple[str, ...]


_SKETCHES: dict[tuple[int, int], tuple[str, tuple[str, ...]]] = {
    (2, 1): ("p", ()),
    (1, 1): ("lowpass", ("filter",)),
    (2, 2): ("pi", ("integral",)),
    (1, 3): ("leadlag", ("lag",)),
    (1, 2): ("rate_limiter", ("limited_output",)),
    (2, 3): ("deadband_pi", ("integral",)),
    (2, 4): ("pid", ("integral", "derivative_filter")),
    (3, 4): ("cascade_pi", ("outer_integral", "inner_integral")),
    (3, 5): ("gain_scheduled_pi", ("integral",)),
    (3, 6): ("limpid", ("integral", "derivative_filter")),
    (2, 7): ("antiwindup_pid", ("integral_term", "derivative_filter")),
}
_SATURATING_KINDS = {"rate_limiter", "limpid", "antiwindup_pid"}


def isolate_primitives(
    decompiled_c: str, input_count: int, parameter_count: int
) -> ControllerSketch:
    """Recognize a supported controller topology and construct a typed AST sketch.

    FMI causalities establish the typed symbol counts. Decompiled arithmetic
    establishes state, branching, and saturation features. Unknown signatures
    fail closed rather than being mislabeled.
    """
    lowered = decompiled_c.lower()
    has_minimum = "fmin" in lowered
    has_maximum = "fmax" in lowered or ("if (" in lowered and "<=" in lowered and has_minimum)
    assignment_pattern = re.compile(
        r"(?:^|[;{])\s*(?:[a-z_][a-z0-9_]*|dat_[0-9a-f]+)\s*=",
        re.IGNORECASE | re.MULTILINE,
    )
    assignment_count = len(assignment_pattern.findall(decompiled_c))
    signature = (input_count, parameter_count)
    if signature not in _SKETCHES:
        raise ValueError(
            "unsupported controller signature: "
            f"{input_count} inputs and {parameter_count} parameters"
        )
    kind, states = _SKETCHES[signature]
    has_saturation = has_minimum and (has_maximum or kind in _SATURATING_KINDS)
    if kind in _SATURATING_KINDS and not has_minimum:
        raise ValueError(f"decompiled {kind} controller is missing saturation primitives")

    arithmetic = [operator for operator in ("+", "-", "*") if operator in lowered]
    operators = (*arithmetic, *(("min", "max") if has_saturation else ()))
    return ControllerSketch(
        kind=kind,
        input_symbols=tuple(f"u{index}" for index in range(input_count)),
        parameter_symbols=tuple(f"p{index}" for index in range(parameter_count)),
        state_symbols=states,
        has_saturation=has_saturation,
        decompiled_assignments=assignment_count,
        operators=operators,
    )
