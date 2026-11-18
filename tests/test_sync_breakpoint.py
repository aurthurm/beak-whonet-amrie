"""Breakpoint organism-code resolution and ALL-organism tests (upstream sync).

Covers the ports of ``Breakpoint.ResolveOrganismCodeType`` and the ``ALL`` clause in
``Breakpoint.GetApplicableBreakpoints``.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd
import pytest

from amrie import breakpoint as bp_mod
from amrie.breakpoint import BREAKPOINTS, get_applicable_breakpoints
from amrie.organism import CURRENT_ORGANISMS
from amrie.paths import resource_path


@pytest.fixture(scope="module")
def raw_breakpoint_rows() -> pd.DataFrame:
    """Built-in breakpoint rows exactly as declared in the resource file (before resolution)."""
    return pd.read_csv(
        resource_path("Breakpoints.txt"),
        sep="\t",
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        quotechar='"',
    )


class TestOrganismCodeTypeResolution:
    def test_bs_minus_retyped_from_genus_code_to_species_group(self, raw_breakpoint_rows):
        raw = raw_breakpoint_rows[raw_breakpoint_rows.ORGANISM_CODE == "BS-"]
        assert Counter(raw.ORGANISM_CODE_TYPE)["GENUS_CODE"] == 104

        resolved = [bp for bp in BREAKPOINTS if bp.ORGANISM_CODE == "BS-"]
        assert len(resolved) == len(raw)
        assert Counter(bp.ORGANISM_CODE_TYPE for bp in resolved) == {"SPECIES_GROUP": 410}

    def test_nme_retyped_from_whonet_org_code_to_serovar_group(self, raw_breakpoint_rows):
        raw = raw_breakpoint_rows[raw_breakpoint_rows.ORGANISM_CODE == "NME"]
        assert Counter(raw.ORGANISM_CODE_TYPE)["WHONET_ORG_CODE"] == 77

        resolved = [bp for bp in BREAKPOINTS if bp.ORGANISM_CODE == "NME"]
        assert len(resolved) == len(raw)
        assert Counter(bp.ORGANISM_CODE_TYPE for bp in resolved)["SEROVAR_GROUP"] == 177

    def test_only_expected_rows_are_retyped(self, raw_breakpoint_rows):
        raw_types = raw_breakpoint_rows.ORGANISM_CODE_TYPE.tolist()
        resolved_types = [bp.ORGANISM_CODE_TYPE for bp in BREAKPOINTS]
        assert len(raw_types) == len(resolved_types)

        changed = Counter(
            (raw_code, raw_type, new_type)
            for raw_code, raw_type, new_type in zip(
                raw_breakpoint_rows.ORGANISM_CODE.tolist(), raw_types, resolved_types
            )
            if raw_type != new_type
        )
        assert changed == {
            ("BS-", "GENUS_CODE", "SPECIES_GROUP"): 104,
            ("NME", "WHONET_ORG_CODE", "SEROVAR_GROUP"): 77,
        }

    def test_all_type_rows_unchanged(self):
        assert sum(1 for bp in BREAKPOINTS if bp.ORGANISM_CODE_TYPE == "ALL") == 515

    def test_user_defined_types_are_not_resolved(self, tmp_path):
        """User-defined files keep the declared organism code type even when it matches nothing."""
        header = "\t".join(
            [
                "GUIDELINES", "YEAR", "TEST_METHOD", "POTENCY", "ORGANISM_CODE", "ORGANISM_CODE_TYPE",
                "BREAKPOINT_TYPE", "HOST", "SITE_OF_INFECTION", "REFERENCE_TABLE", "REFERENCE_SEQUENCE",
                "WHONET_ABX_CODE", "WHONET_TEST", "R", "I", "SDD", "S", "ECV_ECOFF",
                "ECV_ECOFF_TENTATIVE", "DATE_ENTERED", "DATE_MODIFIED", "COMMENTS",
            ]
        )
        row = "\t".join(
            [
                "CLSI", "2020", "MIC", "", "NME", "WHONET_ORG_CODE", "Human", "Human", "", "", "",
                "PEN", "PEN_NM", "0.5", "", "", "0.06", "", "", "", "", "",
            ]
        )
        path = tmp_path / "user.txt"
        path.write_text(f"{header}\n{row}\n", encoding="utf-8")

        loaded_user = bp_mod.load_breakpoints(path, user_defined=True)
        loaded_builtin = bp_mod.load_breakpoints(path, user_defined=False)

        assert loaded_user[0].ORGANISM_CODE_TYPE == "WHONET_ORG_CODE"
        assert loaded_builtin[0].ORGANISM_CODE_TYPE == "SEROVAR_GROUP"

    def test_resolve_keeps_declared_type_when_it_matches(self):
        assert bp_mod._resolve_organism_code_type("nme", "WHONET_ORG_CODE") == "WHONET_ORG_CODE"

    def test_resolve_keeps_declared_type_when_ambiguous_or_unmatched(self):
        assert bp_mod._resolve_organism_code_type("NOT_A_CODE", "GENUS_CODE") == "GENUS_CODE"


class TestAllOrganismsBreakpoints:
    def test_all_organisms_breakpoint_applies_to_organism_without_specific_match(self):
        # 'eco' has no organism-specific EUCAST PEN_EM breakpoint, so only the ALL rows apply.
        applicable = get_applicable_breakpoints(
            "eco",
            [],
            prioritized_guidelines=["EUCAST"],
            prioritized_whonet_abx_full_drug_codes=["PEN_EM"],
        )
        assert applicable
        assert all(bp.ORGANISM_CODE == "ALL" and bp.ORGANISM_CODE_TYPE == "ALL" for bp in applicable)
        assert all(bp.WHONET_TEST == "PEN_EM" for bp in applicable)

    def test_all_organisms_breakpoint_sorts_after_organism_specific(self):
        all_bp = next(
            bp for bp in BREAKPOINTS
            if bp.ORGANISM_CODE_TYPE == "ALL" and bp.WHONET_TEST == "PEN_EM" and bp.GUIDELINES == "EUCAST"
        )
        specific_bp = next(
            bp for bp in BREAKPOINTS
            if bp.ORGANISM_CODE == "NME" and bp.ORGANISM_CODE_TYPE == "SEROVAR_GROUP" and bp.WHONET_TEST == "PEN_EM"
        )
        assert bp_mod._organism_specificity_rank(all_bp) == 9
        assert bp_mod._organism_specificity_rank(specific_bp) < bp_mod._organism_specificity_rank(all_bp)

        # When a specific breakpoint applies, the ALL row for the same group is dropped.
        nme = get_applicable_breakpoints(
            "nme",
            [],
            prioritized_guidelines=["EUCAST"],
            prioritized_whonet_abx_full_drug_codes=["PEN_EM"],
        )
        assert nme
        assert all(bp.ORGANISM_CODE_TYPE != "ALL" for bp in nme)

    def test_all_organisms_match_any_current_organism(self):
        all_bp = next(bp for bp in BREAKPOINTS if bp.ORGANISM_CODE_TYPE == "ALL")
        assert all(bp_mod._organism_matches(all_bp, o) for o in list(CURRENT_ORGANISMS.values())[:500])


class TestNmeBreakpointApplies:
    def test_nme_breakpoint_applies_to_nme_organism_code(self):
        applicable = get_applicable_breakpoints(
            "nme",
            [],
            prioritized_guidelines=["EUCAST"],
            prioritized_whonet_abx_full_drug_codes=["PEN_EM"],
        )
        nme_rows = [bp for bp in applicable if bp.ORGANISM_CODE == "NME"]
        assert nme_rows
        assert all(bp.ORGANISM_CODE_TYPE == "SEROVAR_GROUP" for bp in nme_rows)
