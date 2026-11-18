"""Every interpretation quoted in README.md and docs/ — so the documentation cannot go stale.

If a bundled-table update or an upstream sync changes one of these results, this
test fails and the corresponding example in the docs must be updated with it.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from amrie import interpret_file, interpret_qc_single, interpret_single
from amrie.breakpoint import BREAKPOINTS, get_applicable_breakpoints
from amrie.config import read_configuration
from amrie.io_library import interpret_isolates, load_input_file
from amrie.isolate import IsolateInterpretation

RESOURCES = Path(__file__).resolve().parents[1] / "src" / "amrie" / "resources"
SAMPLE_CONFIG = RESOURCES / "SampleConfig.json"


@pytest.fixture(scope="module")
def config():
    return read_configuration(SAMPLE_CONFIG)


# (organism, antibiotic, measurement, expected) — SampleConfig, guideline year 2026.
SINGLE_EXAMPLES = [
    ("eco", "AMP_ND10", "19", "S"),
    ("eco", "AMP_ND10", "15", "I"),
    ("eco", "AMP_ND10", "12", "R"),
    ("eco", "AMP_ND10", "8", "R"),
    ("eco", "AMP_ND10", "abc", ""),
    ("zzz", "AMP_ND10", "19", ""),
    ("eco", "AMP_ED10", "19", "S"),
    ("eco", "AMP_NM", "8", "S"),
    ("eco", "AMP_NM", "32", "R"),
    ("eco", "AMP_NM", "<=2", "S"),
    ("eco", "AMP_NM", "<2", "S"),
    ("eco", "AMP_NM", "≤2", "S"),
    ("eco", "AMP_NM", "<=8", "S"),
    ("eco", "AMP_NM", "<=16", "S?"),
    ("eco", "AMP_NM", ">8", "NS"),
    ("eco", "AMP_NM", ">16", "R"),
    ("eco", "AMP_NM", ">32", "R"),
    ("eco", "AMP_NM", ">=8", "R?"),
    ("eco", "AMP_NM", ">=32", "R"),
    ("eco", "CTX_ND30", "20", "R"),
    ("eco", "AMK_ND30", "17", "I"),
    ("eco", "CIP_EM", "0.75", "R"),
    ("eco", "CIP_NM", "0.75", "R"),
    ("kpn", "AMP_ND10", "25", "R*"),
    ("kpn", "AMP_NM", "2", "R*"),
    ("spn", "AMC_NM", "2", "S"),
    ("sau", "FOX_ND30", "15", "R!"),
    ("sau", "FOX_ND30", "25", "S"),
    ("sau", "PEN_ND10", "35", "S"),
    ("sau", "CPT_ND30", "26", "S"),
    ("sau", "CPT_ND30", "22", "SDD"),
    ("sau", "CPT_ND30", "18", "R"),
    ("ent", "PEN_ND10", "19", "S"),
    ("ent", "ERY_ND15", "17", "I"),
    ("nme", "PEN_EM", "0.25", "S"),
    ("eco", "PEN_EM", "0.5", ""),  # no EUCAST 2026 breakpoint for E. coli (see Known limitations)
]


@pytest.mark.parametrize(("organism", "antibiotic", "measurement", "expected"), SINGLE_EXAMPLES)
def test_single_examples(config, organism, antibiotic, measurement, expected):
    assert interpret_single(config, organism, antibiotic, measurement) == expected


def test_config_path_accepted():
    assert interpret_single(str(SAMPLE_CONFIG), "ent", "PEN_ND10", "19") == "S"


def test_option_examples(config):
    no_rounding = dataclasses.replace(config, round_half_dilutions=False)
    assert interpret_single(no_rounding, "eco", "CIP_EM", "0.75") == "I"

    no_intrinsic = dataclasses.replace(config, use_intrinsic_resistance_rules=False)
    assert interpret_single(no_intrinsic, "kpn", "AMP_ND10", "25") == "S"
    assert interpret_single(no_intrinsic, "kpn", "AMP_ND10", "10") == "R"

    ecoff_only = dataclasses.replace(config, prioritized_breakpoint_types=["ECOFF"])
    assert interpret_single(ecoff_only, "eco", "AMP_NM", "8") == "WT"
    assert interpret_single(ecoff_only, "eco", "AMP_NM", "32") == "NWT"

    eucast_2020 = dataclasses.replace(config, guideline_year=2020)
    # ALL/ALL PK/PD breakpoint (EUCAST 2020): imipenem-relebactam S<=2, R>4.
    assert interpret_single(eucast_2020, "eco", "IMR_EM", "1") == "S"
    assert interpret_single(eucast_2020, "eco", "IMR_EM", "16") == "R"


def test_qc_examples():
    assert interpret_qc_single("atcc25922", "AMP_ND10", "18") == "IN"
    assert interpret_qc_single("atcc25922", "AMP_ND10", "10") == "OUT"
    assert interpret_qc_single("atcc25922", "AMP_ND10", "x") == ""


def test_eco_amp_disk_breakpoint_rows():
    rows = get_applicable_breakpoints(
        "eco",
        [],
        prioritized_guidelines=["CLSI"],
        prioritized_guideline_years=[2026],
        prioritized_whonet_abx_full_drug_codes=["AMP_ND10"],
    )
    human = rows[0]
    assert (human.ORGANISM_CODE, human.ORGANISM_CODE_TYPE, human.BREAKPOINT_TYPE) == ("EBC", "FAMILY_CODE", "Human")
    assert (str(human.R), human.I, str(human.S)) == ("13", "14-16", "17")


def test_all_organism_breakpoint_counts():
    all_type = [b for b in BREAKPOINTS if b.ORGANISM_CODE_TYPE == "ALL"]
    assert len(all_type) == 515
    assert sum(b.ORGANISM_CODE == "ALL" for b in all_type) == 320  # matched (EUCAST 2013-2020, SFM 2020)
    assert sum(b.ORGANISM_CODE == "Gen" for b in all_type) == 195  # EUCAST 2022-2026, not matched


# --- expert-rule walkthroughs (docs/expert-rules.md) -------------------------------------

EXPERT_EXAMPLES = [
    (
        ["ESBL-CONFIRMED"],
        {"ORGANISM": "eco", "ESBL": "+", "CTX_ND30": "30", "MAN_ND30": "25", "AMP_ND10": "19", "CIP_ND5": "30"},
        {"MAN_ND30": "R!", "CTX_ND30": "S", "CIP_ND5": "S", "AMP_ND10": "S"},
    ),
    (
        ["ESBL-CONFIRMED"],
        {"ORGANISM": "eco", "ESBL": "-", "CTX_ND30": "30", "MAN_ND30": "25"},
        {"CTX_ND30": "S", "MAN_ND30": "S"},
    ),
    (
        ["ESBL-AMPC-PROBABLE"],
        {"ORGANISM": "eco", "CTX_ND30": "20", "MAN_ND30": "25", "CFP_ND75": "30"},
        {"CTX_ND30": "R", "MAN_ND30": "R!", "CFP_ND75": "R!"},
    ),
    (
        ["BLNAR-HFLU"],
        {"ORGANISM": "hin", "BETA_LACT": "-", "AMP_ND10": "15", "AMC_ND20": "25", "CXM_ND30": "25"},
        {"AMP_ND10": "R", "AMC_ND20": "R!", "CXM_ND30": "R!"},
    ),
    (
        ["BLNAR-HFLU"],
        {"ORGANISM": "hin", "BETA_LACT": "+", "AMP_ND10": "15", "AMC_ND20": "25"},
        {"AMP_ND10": "R", "AMC_ND20": ""},
    ),
    (
        ["MRS"],
        {"ORGANISM": "sau", "MECA_PCR": "+", "PEN_ND10": "35", "CPT_ND30": "25", "VAN_NM": "1"},
        {"PEN_ND10": "R!", "VAN_NM": "S", "CPT_ND30": "S"},
    ),
    (
        ["ICR"],
        {"ORGANISM": "sau", "INDUC_CLI": "+", "ERY_ND15": "25", "CLI_ND2": "25", "VAN_NM": "1"},
        {"ERY_ND15": "R!", "CLI_ND2": "R!", "VAN_NM": "S"},
    ),
    (
        [],
        {"ORGANISM": "sau", "INDUC_CLI": "+", "ERY_ND15": "25", "CLI_ND2": "25"},
        {"ERY_ND15": "S", "CLI_ND2": "S"},
    ),
]


@pytest.mark.parametrize(("rules", "row", "expected"), EXPERT_EXAMPLES)
def test_expert_rule_examples(rules, row, expected):
    result = IsolateInterpretation(row, list(row), rules, [], guideline_year=2026).get_all_interpretations()
    assert result == expected


# --- file examples (README five-minute tour, docs/data-formats.md) -----------------------

ISOLATES = (
    "ORGANISM|SPEC_TYPE|AMP_ND10|CTX_ND30|CIP_NM|FOX_ND30|PEN_ND10\n"
    "eco|ur|19|20|0.5||\n"
    "kpn|bl|25|30|<=0.25||\n"
    "sau|wd|||1|15|35\n"
)

HORIZONTAL = (
    "ORGANISM\tSPEC_TYPE\tAMP_ND10\tAMP_ND10_INTERP\tCTX_ND30\tCTX_ND30_INTERP\tCIP_NM\tCIP_NM_INTERP"
    "\tFOX_ND30\tFOX_ND30_INTERP\tPEN_ND10\tPEN_ND10_INTERP\n"
    "eco\tur\t19\tS\t20\tR\t0.5\tI\t\t\t\t\n"
    "kpn\tbl\t25\t{kpn_amp}\t30\tS\t<=0.25\tS\t\t\t\t\n"
    "sau\twd\t\t\t\t\t1\tS\t15\t{sau}\t35\t{sau}\n"
)

VERTICAL = (
    "ORGANISM\tSPEC_TYPE\tANTIBIOTIC_CODE\tANTIBIOTIC_MEASUREMENT\tANTIBIOTIC_INTERPRETATION\n"
    "eco\tur\tAMP_ND10\t19\tS\n"
    "eco\tur\tCTX_ND30\t20\tR\n"
    "eco\tur\tCIP_NM\t0.5\tI\n"
    "kpn\tbl\tAMP_ND10\t25\tR*\n"
    "kpn\tbl\tCTX_ND30\t30\tS\n"
    "kpn\tbl\tCIP_NM\t<=0.25\tS\n"
    "sau\twd\tCIP_NM\t1\tS\n"
    "sau\twd\tFOX_ND30\t15\tR!\n"
    "sau\twd\tPEN_ND10\t35\tR!\n"
)


def _config_file(tmp_path: Path, **overrides) -> Path:
    data = json.loads(SAMPLE_CONFIG.read_text(encoding="utf-8"))
    data.pop("$schema", None)
    data.update(overrides)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, HORIZONTAL.format(kpn_amp="R", sau="R")),
        ({"IncludeInterpretationComments": True}, HORIZONTAL.format(kpn_amp="R*", sau="R!")),
        ({"IncludeInterpretationComments": True, "HorizontalAntibioticResults": False}, VERTICAL),
    ],
)
def test_file_examples(tmp_path, overrides, expected):
    data = tmp_path / "isolates.txt"
    data.write_text(ISOLATES, encoding="utf-8")
    out = tmp_path / "results.txt"

    interpret_file(_config_file(tmp_path, **overrides), data, out, delimiter="|")

    assert out.read_text(encoding="utf-8") == expected


# --- input-file behaviours documented in data-formats.md / troubleshooting.md -------------


def test_utf8_bom_is_ignored(tmp_path):
    path = tmp_path / "bom.txt"
    path.write_bytes(b"\xef\xbb\xbfORGANISM|AMP_ND10\neco|19\n")
    columns, rows = load_input_file(str(path), "|")
    assert columns == ["ORGANISM", "AMP_ND10"]
    assert rows == [{"ORGANISM": "eco", "AMP_ND10": "19"}]


def test_rows_shorter_than_header_are_skipped_like_upstream(tmp_path):
    path = tmp_path / "short.txt"
    path.write_text("ORGANISM|AMP_ND10|CTX_ND30\neco|19|20\neco|19\neco|19|\n", encoding="utf-8")
    _, rows = load_input_file(str(path), "|")
    assert rows == [
        {"ORGANISM": "eco", "AMP_ND10": "19", "CTX_ND30": "20"},
        {"ORGANISM": "eco", "AMP_ND10": "19"},  # trailing empty field keeps the column count
    ]


# --- examples added with the full documentation rewrite ------------------------------------

MORE_SINGLE_EXAMPLES = [
    # getting-started.md disk sweep
    *[("eco", "AMP_ND10", mm, cat) for mm, cat in [("19", "S"), ("17", "S"), ("15", "I"), ("14", "I"), ("13", "R"), ("6", "R")]],
    ("eco", "AMP_ND10", "5", ""),       # disk below 6 mm
    ("eco", "AMP_ND10", "81", ""),      # disk above 80 mm
    # intrinsic-resistance.md
    ("pae", "CTX_ND30", "30", "R*"),
    ("pae", "CTX_ED30", "30", "R*"),
    ("efa", "CTX_ND30", "30", "R*"),
    ("efa", "GEN_ND10", "20", "R*"),
    ("efa", "GEH_ND120", "20", "S"),
    ("efa", "AMK_ND30", "20", "R*"),
    ("sau", "ATM_ND30", "30", "R*"),
    ("sau", "COL_NM", "1", "R*"),
    ("lmo", "CFR_NM", "1", "R*"),
    ("pmi", "TCY_ND30", "25", "R*"),
    ("pmi", "NIT_ND300", "20", "R*"),
    ("eco", "AZM_ND15", "20", "R*"),
    ("aov", "AZM_ND15", "20", ""),
    ("sgm", "GEN_ED10", "20", "R*"),
    ("svi", "GEN_ED10", "20", ""),
    # veterinary-only drug (configuration.md, breakpoint-selection.md)
    ("eco", "ENR_ND5", "25", "S"),
    ("eco", "ENR_ND5", "20", "I"),
    ("eco", "ENR_ND5", "14", "R"),
]


@pytest.mark.parametrize(("organism", "antibiotic", "measurement", "expected"), MORE_SINGLE_EXAMPLES)
def test_more_single_examples(config, organism, antibiotic, measurement, expected):
    assert interpret_single(config, organism, antibiotic, measurement) == expected


def test_configuration_examples(config):
    human = dataclasses.replace(config, prioritized_breakpoint_types=["Human"])
    assert [interpret_single(human, "eco", "ENR_ND5", m) for m in ("25", "20", "14")] == ["", "", ""]

    ecoff = dataclasses.replace(config, prioritized_breakpoint_types=["ECOFF"])
    assert interpret_single(ecoff, "eco", "AMP_ND10", "19") == "WT"

    csf = dataclasses.replace(config, prioritized_sites_of_infection=["Meningitis"])
    csf.update_sites_of_infection()
    general = [interpret_single(config, "spn", "PEN_NM", m) for m in ("0.06", "0.12", "1", "4")]
    meningitis = [interpret_single(csf, "spn", "PEN_NM", m) for m in ("0.06", "0.12", "1", "4")]
    assert general == ["S", "S", "S", "I"]
    assert meningitis == ["S", "R", "R", "R"]


def test_sample_user_defined_breakpoints(config):
    from amrie.breakpoint import load_breakpoints

    udb = load_breakpoints(RESOURCES / "SampleUserDefinedBreakpoints.txt", user_defined=True)
    with_udb = dataclasses.replace(config, user_defined_breakpoints=udb)
    assert [interpret_single(config, "afb", "PEN_ND10", m) for m in ("30", "25", "18")] == ["", "", ""]
    assert [interpret_single(with_udb, "afb", "PEN_ND10", m) for m in ("30", "25", "18")] == ["S", "SDD", "R"]


def test_user_defined_new_drug(tmp_path):
    from amrie.breakpoint import load_breakpoints

    header = (RESOURCES / "SampleUserDefinedBreakpoints.txt").read_text(encoding="utf-8-sig").splitlines()[0]
    row = "User-defined\t2026\tMIC\t\tEBC\tFAMILY_CODE\tHuman\tHuman\t\tLocal study\t1\tX_1\tX_1_NM\t8\t4\t\t2\t\t2026-11-18\t\tLocal validation 2026"
    path = tmp_path / "local-breakpoints.txt"
    path.write_text(header + "\n" + row + "\n", encoding="utf-8")
    udb = load_breakpoints(path, user_defined=True)

    def interp(org, value, year=2026):
        return IsolateInterpretation({"ORGANISM": org, "X_1_NM": value}, ["ORGANISM", "X_1_NM"], None, udb,
                                     guideline_year=year).get_all_interpretations()["X_1_NM"]

    assert [interp("eco", v) for v in ("1", "2", "4", "8", "16", "<=2", ">8")] == ["S", "S", "I", "R", "R", "S", "R"]
    assert interp("kpn", "4", year=2019) == "I"   # user-defined rows ignore the year
    assert interp("sau", "4") == ""               # not Enterobacterales


def test_more_qc_examples():
    assert interpret_qc_single("atcc25922", "CIP_NM", "0.008") == "IN"
    assert interpret_qc_single("atcc25922", "CIP_NM", "0.03") == "OUT"
    assert interpret_qc_single("atcc27853", "MEM_NM", "0.5") == "IN"
    assert interpret_qc_single("atcc29212", "VAN_NE", "3") == "IN"
    assert interpret_qc_single("atcc29212", "VAN_NE", "3", round_half_dilutions=False) == "IN"


def test_cli_single_strips_comments_unless_enabled(tmp_path):
    from typer.testing import CliRunner

    from amrie.cli import app

    with_comments = _config_file(tmp_path, IncludeInterpretationComments=True)
    runner = CliRunner()

    def run(cfg, org, abx, value):
        out = tmp_path / "r.json"
        result = runner.invoke(app, ["single", "-c", str(cfg), "--organism", org, "--antibiotic", abx, "-m", value, "-o", str(out)])
        assert result.exit_code == 0, result.output
        return result.output.strip()

    assert run(SAMPLE_CONFIG, "kpn", "AMP_ND10", "25") == "R"
    assert run(with_comments, "kpn", "AMP_ND10", "25") == "R*"
    assert run(SAMPLE_CONFIG, "sau", "FOX_ND30", "15") == "R"
    assert run(with_comments, "sau", "FOX_ND30", "15") == "R!"
    assert run(SAMPLE_CONFIG, "eco", "AMP_NM", "<=16") == "S?"


def test_sample_comparisons(config):
    from collections import Counter

    columns, rows = load_input_file(str(RESOURCES / "SampleInputFile.txt"), "|")
    assert (len(columns), len(rows)) == (71, 622)
    new = interpret_isolates(config, columns, rows)
    old = interpret_isolates(dataclasses.replace(config, guideline_year=2020), columns, rows)
    changed = sum(before[t] != after.get(t) for (_, before), (_, after) in zip(old, new) for t in before)
    assert changed == 181

    def to_eucast(name):
        return name[:4] + "E" + name[5:] if len(name) > 5 and name[3] == "_" and name[4] == "N" else name

    eucast = interpret_isolates(config, [to_eucast(c) for c in columns],
                                [{to_eucast(k): v for k, v in r.items()} for r in rows])
    disagree = Counter(
        (t[:3], c, e[to_eucast(t)])
        for (_, ci), (_, e) in zip(new, eucast)
        for t, c in ci.items()
        if c and e.get(to_eucast(t)) and c != e[to_eucast(t)]
    )
    assert sum(disagree.values()) == 506
    assert disagree.most_common(1) == [(("CIP", "S", "I"), 157)]
