"""Tests for lenient configuration parsing (upstream SampleConfig.json compatibility).

Covers: unknown keys ignored, case-insensitive key names, ``//`` / ``/* */``
comments, trailing commas, and loading upstream's SampleConfig.json.
"""

from __future__ import annotations

import logging

import orjson
import pytest

from amrie.config import _preprocess_json, read_configuration
from amrie.paths import resource_path

# Verbatim copy of upstream AMRIE.Library/Resources/SampleConfig.json.
UPSTREAM_SAMPLE_CONFIG = """{
\t"$schema": "../docs/reference/amrie-config.schema.json",
\t"RoundHalfDilutions": true,
\t"IncludeInterpretationComments": false,
\t"EnabledExpertInterpretationRules": [
\t\t"BLNAR-HFLU",
\t\t"MRS",
\t\t"ICR"
\t],
\t"_Comment_IgnoredExpertInterpretationRules": [
\t\t"ESBL-CONFIRMED",
\t\t"ESBL-AMPC-PROBABLE"
\t],
\t"GuidelineYear": 2026,
\t"PrioritizedBreakpointTypes": [ "Human", "Animal", "ECOFF" ],
\t"PrioritizedSitesOfInfection": [],
\t"DisabledSitesOfInfection": [],
\t"HorizontalAntibioticResults": true,
\t"DISABLED_UserDefinedBreakpointsFile": "Resources\\\\SampleUserDefinedBreakpoints.txt"
}"""


def _write(tmp_path, text: str):
    path = tmp_path / "config.json"
    path.write_text(text, encoding="utf-8")
    return path


def test_upstream_sample_config_loads(tmp_path):
    config = read_configuration(_write(tmp_path, UPSTREAM_SAMPLE_CONFIG))

    assert config.round_half_dilutions is True
    assert config.include_interpretation_comments is False
    assert config.enabled_expert_interpretation_rules == ["BLNAR-HFLU", "MRS", "ICR"]
    assert config.guideline_year == 2026
    assert config.prioritized_breakpoint_types == ["Human", "Animal", "ECOFF"]
    assert config.horizontal_antibiotic_results is True
    assert config.user_defined_breakpoints_file == ""
    # Empty lists become None (C# null = default order applies).
    assert config.disabled_sites_of_infection is None
    assert config.prioritized_sites_of_infection is None


def test_repo_sample_config_loads_and_declares_schema():
    path = resource_path("SampleConfig.json")
    assert '"$schema"' in path.read_text(encoding="utf-8")

    config = read_configuration(path)
    assert config.guideline_year == 2026
    assert config.enabled_expert_interpretation_rules == ["BLNAR-HFLU", "MRS", "ICR"]


def test_unknown_keys_are_ignored_and_not_logged_as_warnings(tmp_path, caplog):
    text = '{"$schema": "x.json", "NotASetting": 1, "GuidelineYear": 2025}'
    with caplog.at_level(logging.WARNING, logger="amrie.config"):
        config = read_configuration(_write(tmp_path, text))

    assert config.guideline_year == 2025
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_unknown_keys_logged_at_debug(tmp_path, caplog):
    with caplog.at_level(logging.DEBUG, logger="amrie.config"):
        read_configuration(_write(tmp_path, '{"$schema": "x.json"}'))

    assert any("$schema" in r.getMessage() for r in caplog.records)


def test_user_defined_breakpoints_key_is_not_settable_from_json(tmp_path):
    # The dataclass field exists but is not a JSON setting; it must not be passed through.
    config = read_configuration(_write(tmp_path, '{"UserDefinedBreakpoints": [{"a": 1}]}'))
    assert config.user_defined_breakpoints == []


@pytest.mark.parametrize(
    "key",
    ["roundhalfdilutions", "ROUNDHALFDILUTIONS", "RoundHalfDilutions", "round_half_dilutions"],
)
def test_key_names_are_case_insensitive(tmp_path, key):
    config = read_configuration(_write(tmp_path, f'{{"{key}": false}}'))
    assert config.round_half_dilutions is False


def test_mixed_case_keys_in_one_file(tmp_path):
    text = '{"guidelineyear": 2024, "horizontalantibioticresults": false}'
    config = read_configuration(_write(tmp_path, text))
    assert config.guideline_year == 2024
    assert config.horizontal_antibiotic_results is False


def test_line_comments_are_skipped(tmp_path):
    text = """{
        // leading comment
        "GuidelineYear": 2025, // trailing comment
        "RoundHalfDilutions": false
    }"""
    config = read_configuration(_write(tmp_path, text))
    assert config.guideline_year == 2025
    assert config.round_half_dilutions is False


def test_block_comments_are_skipped(tmp_path):
    text = """{
        /* block
           comment */ "GuidelineYear": /* inline */ 2023,
        "RoundHalfDilutions": false /* after */
    }"""
    config = read_configuration(_write(tmp_path, text))
    assert config.guideline_year == 2023
    assert config.round_half_dilutions is False


def test_trailing_commas_in_objects_and_arrays(tmp_path):
    text = """{
        "GuidelineYear": 2022,
        "PrioritizedBreakpointTypes": [ "Human", "Animal", ],
        "EnabledExpertInterpretationRules": [ "MRS", ],
    }"""
    config = read_configuration(_write(tmp_path, text))
    assert config.guideline_year == 2022
    assert config.prioritized_breakpoint_types == ["Human", "Animal"]
    assert config.enabled_expert_interpretation_rules == ["MRS"]


def test_trailing_comma_followed_by_comment(tmp_path):
    text = '{"GuidelineYear": 2021, /* note */ // more\n}'
    config = read_configuration(_write(tmp_path, text))
    assert config.guideline_year == 2021


def test_empty_lists_become_none(tmp_path):
    text = """{
        "EnabledExpertInterpretationRules": [],
        "PrioritizedBreakpointTypes": [],
        "PrioritizedSitesOfInfection": [],
        "DisabledSitesOfInfection": []
    }"""
    config = read_configuration(_write(tmp_path, text))
    assert config.enabled_expert_interpretation_rules is None
    assert config.prioritized_breakpoint_types is None
    assert config.disabled_sites_of_infection is None


def test_comment_prefixed_and_disabled_keys_are_ignored(tmp_path):
    text = """{
        "_Comment_Anything": ["x"],
        "DISABLED_UserDefinedBreakpointsFile": "missing.txt",
        "GuidelineYear": 2020
    }"""
    config = read_configuration(_write(tmp_path, text))
    assert config.guideline_year == 2020
    assert config.user_defined_breakpoints_file == ""


def test_utf8_bom_is_accepted(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b'\xef\xbb\xbf{"GuidelineYear": 2019}')
    assert read_configuration(path).guideline_year == 2019


# --- _preprocess_json unit tests -------------------------------------------------


def test_preprocess_keeps_comment_markers_inside_strings():
    text = '{"url": "http://example.com/a//b", "x": "/* not a comment */"}'
    assert _preprocess_json(text) == text


def test_preprocess_handles_escaped_quotes_inside_strings():
    text = '{"a": "quote \\" // still string", "b": 1}'
    assert _preprocess_json(text) == text


def test_preprocess_strips_comments_and_trailing_commas():
    text = '{"a": [1, 2, /* c */ ], // end\n"b": 3,}'
    assert orjson.loads(_preprocess_json(text)) == {"a": [1, 2], "b": 3}


def test_preprocess_url_value_round_trips_through_reader(tmp_path):
    # A "//" inside a value must survive preprocessing (it is an unknown key here,
    # so the test checks that parsing succeeds and the defaults are intact).
    text = '{"$schema": "https://example.com/schema.json", "GuidelineYear": 2018}'
    assert read_configuration(_write(tmp_path, text)).guideline_year == 2018
