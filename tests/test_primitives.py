import pytest

from construct_demo.primitives import isolate_primitives


def test_isolates_pi_from_two_assignments() -> None:
    sketch = isolate_primitives("void f(){ DAT_1 = DAT_2 + DAT_3; DAT_4 = DAT_1 * DAT_5; }", 2, 2)
    assert sketch.kind == "pi"
    assert sketch.input_symbols == ("u0", "u1")


def test_isolates_pid_from_three_assignments() -> None:
    source = """void f(){
      DAT_1 = DAT_1 + DAT_2;
      DAT_3 = DAT_3 + DAT_4;
      DAT_5 = DAT_1 + DAT_3;
    }"""
    assert isolate_primitives(source, 2, 4).kind == "pid"


def test_isolates_limpid_from_saturation_primitives() -> None:
    source = """void f(){
      DAT_1 = DAT_1 + DAT_2;
      DAT_3 = DAT_3 + DAT_4;
      DAT_5 = fmin(fmax(DAT_6, DAT_7), DAT_8);
    }"""
    sketch = isolate_primitives(source, 3, 6)
    assert sketch.kind == "limpid"
    assert sketch.has_saturation


def test_isolates_compiler_lowered_saturation() -> None:
    source = """void f(){
      DAT_1 = DAT_1 + DAT_2;
      DAT_3 = DAT_3 + DAT_4;
      dVar1 = DAT_5;
      if (dVar1 <= DAT_6) { dVar1 = DAT_6; }
      DAT_7 = NEON_fminnm(dVar1, DAT_8);
    }"""
    assert isolate_primitives(source, 3, 6).kind == "limpid"


def test_accepts_decompiler_omitted_lower_clamp_for_saturation_family() -> None:
    source = """void f(){
      DAT_1 = DAT_1 + DAT_2;
      DAT_3 = NEON_fminnm(DAT_4, DAT_5);
      DAT_6 = DAT_6 + DAT_7;
    }"""
    sketch = isolate_primitives(source, 2, 7)
    assert sketch.kind == "antiwindup_pid"
    assert sketch.has_saturation


def test_rejects_unknown_controller_signature() -> None:
    with pytest.raises(ValueError, match="unsupported controller signature"):
        isolate_primitives("void f(){ DAT_1 = DAT_2; }", 4, 9)
