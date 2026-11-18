"""Tests for upstream-sync ABX_CODE_TYPE resolution in expected_resistance.

Mirrors ``ResolveAntibioticCodeType`` in ``ExpectedResistancePhenotypeRule.cs``.
"""

from types import SimpleNamespace

import pandas as pd
import pytest

from amrie.antibiotic import ALL_ANTIBIOTICS
from amrie.expected_resistance import (
    EXPECTED_RESISTANCE_PHENOTYPE_RULES,
    get_applicable_expected_resistance_rules,
    resolve_antibiotic_code_type,
)
from amrie.paths import resource_path


def _fake(whonet: str, atc: str) -> SimpleNamespace:
    return SimpleNamespace(WHONET_ABX_CODE=whonet, ATC_CODE=atc)


def _find_rule(guideline: str, organism: str, abx: str):
    matches = [
        r
        for r in EXPECTED_RESISTANCE_PHENOTYPE_RULES
        if r.GUIDELINE == guideline and r.ORGANISM_CODE == organism and r.ABX_CODE == abx
    ]
    assert len(matches) == 1, (guideline, organism, abx, len(matches))
    return matches[0]


# --- Real-data retypes -------------------------------------------------------


def test_real_data_retypes_exactly_three_rules():
    raw = pd.read_csv(
        resource_path("ExpectedResistancePhenotypes.txt"),
        sep="\t",
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        quotechar='"',
    )
    declared = list(raw["ABX_CODE_TYPE"])
    resolved = [r.ABX_CODE_TYPE for r in EXPECTED_RESISTANCE_PHENOTYPE_RULES]
    assert len(declared) == len(resolved)
    changed = [
        (raw.iloc[i]["GUIDELINE"], raw.iloc[i]["ORGANISM_CODE"], raw.iloc[i]["ABX_CODE"], declared[i], resolved[i])
        for i in range(len(declared))
        if declared[i] != resolved[i]
    ]
    assert len(changed) == 3, changed


def test_clsi_lmo_j01db_retyped_to_atc():
    rule = _find_rule("CLSI", "lmo", "J01DB")
    assert rule.ABX_CODE_TYPE == "ATC_CODE"


def test_eucast_str_gen_retyped_to_whonet():
    rule = _find_rule("EUCAST", "STR", "GEN")
    assert rule.ORGANISM_CODE_TYPE == "GENUS_CODE"
    assert rule.ABX_CODE_TYPE == "WHONET_ABX_CODE"


def test_eucast_str_geh_retyped_to_whonet():
    rule = _find_rule("EUCAST", "STR", "GEH")
    assert rule.ORGANISM_CODE_TYPE == "GENUS_CODE"
    assert rule.ABX_CODE_TYPE == "WHONET_ABX_CODE"


def test_j01db_rule_makes_first_gen_cephalosporin_intrinsically_resistant():
    # Cefadroxil (CFR, ATC J01DB05) is a first-generation cephalosporin. Before the
    # retype the CLSI lmo J01DB rule was treated as a WHONET code and never expanded.
    rules = get_applicable_expected_resistance_rules("lmo", ["CLSI"], ["CFR"])
    assert any(r.GUIDELINE == "CLSI" and r.ABX_CODE == "CFR" for r in rules)


# --- Resolver unit tests -----------------------------------------------------


def test_declared_whonet_kept_when_whonet_matches():
    assert resolve_antibiotic_code_type("CFR", "WHONET_ABX_CODE") == "WHONET_ABX_CODE"


def test_declared_atc_kept_when_atc_matches():
    assert resolve_antibiotic_code_type("J01DB", "ATC_CODE") == "ATC_CODE"


def test_wrong_declared_type_switches_to_unique_match():
    catalogue = [_fake("ABC", "J01AA01"), _fake("XYZ", "")]
    assert resolve_antibiotic_code_type("J01AA", "WHONET_ABX_CODE", catalogue) == "ATC_CODE"
    assert resolve_antibiotic_code_type("ABC", "ATC_CODE", catalogue) == "WHONET_ABX_CODE"


def test_empty_atc_code_does_not_count_as_atc_match():
    catalogue = [_fake("XYZ", "")]
    assert resolve_antibiotic_code_type("XYZ", "ATC_CODE", catalogue) == "WHONET_ABX_CODE"


def test_ambiguous_key_keeps_declared_type_when_declared_matches():
    # "AB" matches both a WHONET code and an ATC prefix; the declared type is confirmed, so it is kept.
    catalogue = [_fake("AB", "AB12"), _fake("CDE", "ABC")]
    assert resolve_antibiotic_code_type("AB", "WHONET_ABX_CODE", catalogue) == "WHONET_ABX_CODE"
    assert resolve_antibiotic_code_type("AB", "ATC_CODE", catalogue) == "ATC_CODE"


def test_ambiguous_key_raises_when_both_match_and_declared_unconfirmed():
    catalogue = [_fake("AB", "AB12"), _fake("CDE", "ABC")]
    with pytest.raises(ValueError, match="cannot be resolved uniquely"):
        resolve_antibiotic_code_type("AB", "", catalogue)


def test_unknown_key_raises_when_neither_matches():
    catalogue = [_fake("ABC", "J01AA01")]
    with pytest.raises(ValueError, match="'QQQ' with type 'ATC_CODE' cannot be resolved uniquely"):
        resolve_antibiotic_code_type("QQQ", "ATC_CODE", catalogue)


def test_default_catalogue_is_all_antibiotics():
    # Sanity: default path uses the real catalogue.
    assert resolve_antibiotic_code_type("CFR", "WHONET_ABX_CODE") == "WHONET_ABX_CODE"
    assert any(a.WHONET_ABX_CODE == "CFR" for a in ALL_ANTIBIOTICS)
