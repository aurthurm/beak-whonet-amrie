"""Port of ``UserDefinedAntibioticTests.cs``.

User-defined antibiotic columns are ``X_1`` ... ``X_99`` with no leading zero.
"""

from __future__ import annotations

import pytest

from amrie.antibiotic import short_code
from amrie.expert_rule import ExpertInterpretationRule, ExpertRuleCriterion
from amrie.parsing import (
    VALID_ANTIBIOTIC_CODE_REGEX,
    VALID_ANTIBIOTIC_FIELD_NAME_REGEX,
    AntibioticComponents,
)


@pytest.mark.parametrize(
    "field_name",
    [
        "PEN_ND10",
        "AMK_ED30",
        "AMP_EM",
        "FOX_FE",
        "CRO_NM",
        "VAN_NE",
        "X_1_ND10",
        "X_2_EM",
        "X_99_FE",
        "X_10_NM",
        "X_5_ED25",
        "x_1_NM",
    ],
)
def test_field_name_regex_matches_valid_names(field_name: str) -> None:
    assert VALID_ANTIBIOTIC_FIELD_NAME_REGEX.match(field_name), field_name


@pytest.mark.parametrize(
    "field_name",
    [
        "X__ND10",  # no digit
        "X_0_ND10",  # single digit zero
        "X_00_ND10",  # leading zero
        "X_01_ND10",  # leading zero
        "X_05_ED25",  # leading zero
        "X_100_ND10",  # three digits
        "X_AA_ND10",  # non-numeric
        "X_ND10",  # missing number
        "X_1",  # missing guideline and method
        "X_13",  # missing guideline and method
        "PEN_NC",  # invalid test method 'C'
        "PEN_NF",  # invalid test method 'F'
        "PEN_",  # trailing underscore only
        "P_ND10",  # short antibiotic code
    ],
)
def test_field_name_regex_rejects_invalid_names(field_name: str) -> None:
    assert not VALID_ANTIBIOTIC_FIELD_NAME_REGEX.match(field_name), field_name


@pytest.mark.parametrize("code", ["PEN", "AMK", "AMP", "CRO", "X_1", "X_2", "X_10", "X_99"])
def test_code_regex_matches_valid_codes(code: str) -> None:
    assert VALID_ANTIBIOTIC_CODE_REGEX.match(code), code


@pytest.mark.parametrize("code", ["X_0", "X_00", "X_01", "X_09", "X_100", "X_AA", "PE", "PENN"])
def test_code_regex_rejects_invalid_codes(code: str) -> None:
    assert not VALID_ANTIBIOTIC_CODE_REGEX.match(code), code


@pytest.mark.parametrize(
    ("full_code", "expected"),
    [
        ("X_1_ND10", "X_1"),
        ("X_2_EM", "X_2"),
        ("X_10_NM", "X_10"),
        ("X_99_FE", "X_99"),
        ("X_1", "X_1"),
        ("X_10", "X_10"),
        ("X_99", "X_99"),
        ("PEN_ND10", "PEN"),
        ("AMK_ED30", "AMK"),
        ("CRO_NM", "CRO"),
        ("PEN", "PEN"),
        ("x_12_nm", "x_12"),
    ],
)
def test_short_code(full_code: str, expected: str) -> None:
    assert short_code(full_code) == expected


def test_components_parses_standard_antibiotic() -> None:
    c = AntibioticComponents("PEN_ND10")
    assert c.code == "PEN"
    assert c.guideline == "CLSI"
    assert c.test_method == "DISK"


def test_components_parses_user_defined_antibiotic() -> None:
    c = AntibioticComponents("X_1_ND10")
    assert c.code == "X_1"
    assert c.guideline == "CLSI"
    assert c.test_method == "DISK"

    c = AntibioticComponents("X_2_EM")
    assert c.code == "X_2"
    assert c.guideline == "EUCAST"
    assert c.test_method == "MIC"

    c = AntibioticComponents("X_10_NM")
    assert c.code == "X_10"
    assert c.guideline == "CLSI"
    assert c.test_method == "MIC"


def test_components_user_defined_detection_is_case_insensitive() -> None:
    c = AntibioticComponents("x_1_NM")
    assert c.code == "x_1"
    assert c.guideline == "CLSI"
    assert c.test_method == "MIC"


@pytest.mark.parametrize(
    "invalid_code",
    [
        "X_0_ND10",
        "X_00_ND10",
        "X_01_ND10",
        "X_09_FE",
        "X_100_ND10",
        "X_AB_ND10",
        "X_ND10",
        "X_1",  # too few components
        "INVALID",  # no underscore
        "PEN_NC",  # unknown test method
    ],
)
def test_components_rejects_invalid_codes(invalid_code: str) -> None:
    with pytest.raises(ValueError):
        AntibioticComponents(invalid_code)


def test_components_user_defined_error_message_matches_csharp() -> None:
    with pytest.raises(ValueError, match=r"must follow the pattern X_# or X_## \(e\.g\., X_1 or X_12\)"):
        AntibioticComponents("X_0_ND10")


def test_components_rejects_none() -> None:
    with pytest.raises(ValueError):
        AntibioticComponents(None)  # type: ignore[arg-type]


def test_components_rejects_missing_guideline_and_method() -> None:
    # Standard code whose guideline+method part is a single character.
    with pytest.raises(ValueError, match="Missing guideline and test method"):
        AntibioticComponents("PEN_N")


def test_x1_and_x12_do_not_collide_in_expert_rule_criteria() -> None:
    """A criterion for X_1 must not fire on an X_12 column, and vice versa."""

    def rule(test_name: str) -> ExpertInterpretationRule:
        return ExpertInterpretationRule(
            RULE_CODE="TEST",
            DESCRIPTION="",
            ORGANISM_CODE="",
            ORGANISM_CODE_TYPE="",
            RULE_CRITERIA=[ExpertRuleCriterion(test_name, "R")],
            CriteriaOperator="AND",
            AFFECTED_ANTIBIOTICS=[],
            ANTIBIOTIC_EXCEPTIONS=[],
        )

    only_x12 = {"X_12_NM": "R"}
    row_x12 = {"X_12_NM": "R"}
    assert rule("X_1").evaluate_criteria(row_x12, only_x12) is False
    assert rule("X_12").evaluate_criteria(row_x12, only_x12) is True

    only_x1 = {"X_1_NM": "R"}
    row_x1 = {"X_1_NM": "R"}
    assert rule("X_1").evaluate_criteria(row_x1, only_x1) is True
    assert rule("X_12").evaluate_criteria(row_x1, only_x1) is False
