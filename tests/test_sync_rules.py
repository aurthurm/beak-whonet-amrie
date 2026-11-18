"""Regression tests for breakpoint-cache keying and round_half_dilutions threading.

Covers the C# ``BreakpointLookup`` behaviour where the cache key includes the
drug code, prioritized breakpoint types, prioritized sites of infection and the
user-defined breakpoints, plus the E-test half-dilution option being passed
through from the configuration to the rules engine.
"""

from __future__ import annotations

import dataclasses
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from amrie import constants as C
from amrie.antibiotic_rules import (
    _breakpoint_cache,
    _make_selection_key,
    clear_breakpoints,
    preheat_breakpoint_cache,
)
from amrie.breakpoint import BreakpointTypes, GuidelineNames, get_applicable_breakpoints
from amrie.config import InterpretationConfiguration, read_configuration
from amrie.io_library import interpret_isolates
from amrie.isolate import IsolateInterpretation
from amrie.paths import resource_path

SAMPLE_CONFIG = resource_path("SampleConfig.json")

# eco / AMP_NM / 16 (MIC, CLSI 2026):
#   Human -> I, Animal -> NS, ECOFF -> NWT
AMP_MIC_16_BY_TYPE = {
    ("Human",): "I",
    ("Animal",): "NS",
    ("ECOFF",): "NWT",
}

# eco / CIP_EM / 0.75 (E-test): rounds up to 1 -> R; unrounded 0.75 -> I
CIP_ETEST = "0.75"


@pytest.fixture(autouse=True)
def _fresh_breakpoint_cache():
    clear_breakpoints()
    yield
    clear_breakpoints()


@pytest.fixture(scope="module")
def base_config() -> InterpretationConfiguration:
    return read_configuration(str(SAMPLE_CONFIG))


def _with(config: InterpretationConfiguration, **changes) -> InterpretationConfiguration:
    return dataclasses.replace(config, **changes)


def _interp(config: InterpretationConfiguration, drug: str, value: str) -> str:
    return IsolateInterpretation.get_single_interpretation(config, "eco", drug, value)


# ---------------------------------------------------------------------------
# Task 1: breakpoint cache keyed by selection inputs
# ---------------------------------------------------------------------------


def test_breakpoint_types_do_not_return_stale_breakpoints(base_config):
    """Same organism/drug/year in one process, different breakpoint types."""
    default = _with(base_config, prioritized_breakpoint_types=["Human", "Animal", "ECOFF"])
    animal = _with(base_config, prioritized_breakpoint_types=["Animal"])
    ecoff = _with(base_config, prioritized_breakpoint_types=["ECOFF"])

    assert _interp(default, "AMP_NM", "16") == "I"
    assert _interp(animal, "AMP_NM", "16") == "NS"
    assert _interp(ecoff, "AMP_NM", "16") == "NWT"
    # Going back to the first selection must still return its own result.
    assert _interp(default, "AMP_NM", "16") == "I"


@pytest.mark.parametrize("types", list(AMP_MIC_16_BY_TYPE))
def test_breakpoint_types_match_fresh_cache_result(base_config, types):
    """A cached result equals what a cold cache would compute for the same selection."""
    config = _with(base_config, prioritized_breakpoint_types=list(types))
    expected = AMP_MIC_16_BY_TYPE[types]

    clear_breakpoints()
    cold = _interp(config, "AMP_NM", "16")
    warm = _interp(config, "AMP_NM", "16")

    assert cold == warm == expected


def test_user_defined_breakpoints_do_not_return_stale_breakpoints(base_config):
    """Adding a user-defined breakpoint for the same drug must change the result."""
    builtin = get_applicable_breakpoints(
        "eco",
        [],
        prioritized_guidelines=["CLSI"],
        prioritized_guideline_years=[2026],
        prioritized_whonet_abx_full_drug_codes=["AMP_NM"],
        prioritized_breakpoint_types=["Human"],
        return_first_breakpoint_only=True,
    )[0]
    user_bp = dataclasses.replace(
        builtin,
        GUIDELINES=GuidelineNames.USER_DEFINED,
        ORGANISM_CODE="eco",
        ORGANISM_CODE_TYPE="WHONET_ORG_CODE",
        HOST="Human",
        SITE_OF_INFECTION="",
        BREAKPOINT_TYPE=BreakpointTypes.HUMAN,
        S=Decimal("4"),
        R=Decimal("8"),
    )

    plain = _with(base_config, prioritized_breakpoint_types=["Human"])
    with_user = _with(
        base_config,
        prioritized_breakpoint_types=["Human"],
        user_defined_breakpoints=[user_bp],
        guideline_year=2026,
    )

    # Built-in S<=8 at MIC 6 gives S; user breakpoint (R=8) rounds 6 up to 8 -> R.
    assert _interp(plain, "AMP_NM", "6") == "S"
    assert _interp(with_user, "AMP_NM", "6") == "R"
    assert _interp(plain, "AMP_NM", "6") == "S"


def test_none_and_empty_selection_lists_are_distinct_keys():
    assert _make_selection_key("AMP_NM", None, None, None) != _make_selection_key(
        "AMP_NM", [], [], []
    )
    assert _make_selection_key("AMP_NM", None, None, None) != _make_selection_key(
        "AMP_NM", ["Human"], None, None
    )
    assert _make_selection_key("AMP_NM", None, ["Oral"], None) != _make_selection_key(
        "AMP_NM", None, None, None
    )
    assert _make_selection_key("AMP_NM", None, None, []) != _make_selection_key(
        "AMP_NM", None, None, None
    )


def test_cache_holds_one_entry_per_selection(base_config):
    """Different selections create separate entries; repeat calls do not."""
    types_a = _with(base_config, prioritized_breakpoint_types=["Human"])
    types_b = _with(base_config, prioritized_breakpoint_types=["Animal"])
    sites_none = _with(base_config, prioritized_sites_of_infection=None)
    sites_empty = _with(base_config, prioritized_sites_of_infection=[])

    for cfg in (types_a, types_b, sites_none, sites_empty, types_a, sites_none):
        _interp(cfg, "AMP_NM", "16")

    amp_entries = [k for k in _breakpoint_cache if k[0] == "eco" and k[3][0] == "AMP_NM"]
    assert len(amp_entries) == 4


def test_preheat_then_interpret_with_other_selection(base_config):
    """Preheating one selection must not leak into interpretation under another."""
    keys = [("eco", "CLSI", "AMP_NM"), ("eco", "CLSI", "AMP_NM")]  # duplicate on purpose
    preheat_breakpoint_cache(
        [],
        2026,
        ["Animal"],
        None,
        keys,
    )
    # Warmed for Animal only; a Human-selection lookup must still compute Human.
    human = _with(base_config, prioritized_breakpoint_types=["Human"])
    assert _interp(human, "AMP_NM", "16") == "I"

    animal = _with(base_config, prioritized_breakpoint_types=["Animal"])
    assert _interp(animal, "AMP_NM", "16") == "NS"


def test_concurrent_mixed_selections_return_correct_results(base_config):
    configs = [
        _with(base_config, prioritized_breakpoint_types=list(types))
        for types in AMP_MIC_16_BY_TYPE
    ]
    jobs = [(configs[i % len(configs)], i % len(configs)) for i in range(60)]
    expected = list(AMP_MIC_16_BY_TYPE.values())

    def run(job):
        cfg, idx = job
        return _interp(cfg, "AMP_NM", "16"), expected[idx]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, jobs))

    assert all(got == want for got, want in results)


# ---------------------------------------------------------------------------
# Task 2: round_half_dilutions threaded through
# ---------------------------------------------------------------------------


def test_round_half_dilutions_changes_etest_result(base_config):
    on = _with(base_config, round_half_dilutions=True)
    off = _with(base_config, round_half_dilutions=False)

    assert _interp(on, "CIP_EM", CIP_ETEST) == "R"
    assert _interp(off, "CIP_EM", CIP_ETEST) == "I"


def test_round_half_dilutions_passed_to_isolate_interpretation(base_config):
    row = {C.KeyFields.ORGANISM: "eco", "CIP_EM": CIP_ETEST}
    cols = list(row.keys())
    common = dict(
        data_row_values=row,
        column_names=cols,
        enabled_expert_interpretation_rules=base_config.enabled_expert_interpretation_rules,
        user_defined_breakpoints=base_config.user_defined_breakpoints,
        guideline_year=2026,
        prioritized_breakpoint_types=base_config.prioritized_breakpoint_types,
        prioritized_sites_of_infection=base_config.prioritized_sites_of_infection,
    )

    rounded = IsolateInterpretation(**common, round_half_dilutions=True)
    unrounded = IsolateInterpretation(**common, round_half_dilutions=False)

    assert rounded.get_all_interpretations()["CIP_EM"] == "R"
    assert unrounded.get_all_interpretations()["CIP_EM"] == "I"


def test_round_half_dilutions_default_is_true(base_config):
    row = {C.KeyFields.ORGANISM: "eco", "CIP_EM": CIP_ETEST}
    interp = IsolateInterpretation(
        row,
        list(row.keys()),
        None,
        base_config.user_defined_breakpoints,
        guideline_year=2026,
    )
    assert interp.get_all_interpretations()["CIP_EM"] == "R"


@pytest.mark.parametrize("round_flag", [True, False])
def test_interpret_isolates_honours_config_round_half_dilutions(base_config, round_flag):
    config = _with(base_config, round_half_dilutions=round_flag)
    row = {C.KeyFields.ORGANISM: "eco", "CIP_EM": CIP_ETEST}
    results = interpret_isolates(
        config,
        list(row.keys()),
        [row],
        guideline_year=2026,
        parallel=False,
    )
    _, interps = results[0]
    assert interps["CIP_EM"] == ("R" if round_flag else "I")
