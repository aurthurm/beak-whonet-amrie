"""Expert-rule drug matching in IsolateInterpretation uses exact short codes.

Upstream C# (12f392a) replaced ``key.StartsWith(code)`` with
``ValidAntibioticFieldNameRegex.IsMatch(key) && ShortCode(key) == code`` when
collecting the drugs an expert rule needs evaluated. Prefix matching wrongly
picked up non-antibiotic columns such as ``OXA_SCREEN`` for the ``OXA``
criterion of the MRS rule, and made ``X_1`` match ``X_12_*`` columns.
"""

from __future__ import annotations

from amrie import constants as C
from amrie.isolate import IsolateInterpretation

R_EXPERT = "R!"


def _interpret(row: dict[str, str], rules: list[str]) -> dict[str, str]:
    return IsolateInterpretation(
        row, list(row), rules, [], guideline_year=C.BREAKPOINT_TABLE_REVISION_YEAR
    ).get_all_interpretations()


def test_non_antibiotic_column_sharing_a_drug_prefix_is_not_interpreted():
    # OXA_SCREEN starts with "OXA" (an MRS criterion drug) but is a screening
    # test, not an antibiotic column. Prefix matching tried to interpret it.
    row = {"ORGANISM": "sau", "OXA_SCREEN": "-", "FOX_ND30": "15", "PEN_ND10": "35"}

    interpretations = _interpret(row, ["MRS"])

    assert "OXA_SCREEN" not in interpretations
    # FOX_ND30=15 is NS for S. aureus, so MRS fires and overrides PEN to R!.
    assert interpretations["PEN_ND10"] == R_EXPERT


def test_mrs_rule_still_fires_from_the_real_oxacillin_column():
    row = {"ORGANISM": "sau", "OXA_SCREEN": "-", "OXA_NM": "8", "PEN_ND10": "35"}

    interpretations = _interpret(row, ["MRS"])

    assert "OXA_SCREEN" not in interpretations
    assert interpretations["PEN_ND10"] == R_EXPERT


def test_mrs_rule_does_not_fire_when_criterion_drugs_are_susceptible():
    row = {"ORGANISM": "sau", "OXA_SCREEN": "-", "FOX_ND30": "25", "PEN_ND10": "35"}

    interpretations = _interpret(row, ["MRS"])

    assert interpretations["PEN_ND10"] != R_EXPERT
