"""Web layer: the single tab and /api/interpret/single honour include_comments.

Before this fix the flag reached the configuration but ``interpret_single`` never
strips suffixes, so ``R*`` / ``R!`` were returned even with comments switched off.
"""

from __future__ import annotations

import pytest

pytest.importorskip("nicegui")
# `web` is importable after `pip install -e ".[web]"` (or with the repo root on PYTHONPATH).
_run_single_interpret = pytest.importorskip("web.api.interpret")._run_single_interpret
_helpers = pytest.importorskip("web.helpers")
interpret_for_display = _helpers.interpret_for_display
make_single_tab_config = _helpers.make_single_tab_config
SingleInterpretRequest = pytest.importorskip("web.models.requests").SingleInterpretRequest


def _config(include_comments: bool):
    return make_single_tab_config(
        guideline_year=2026,
        include_comments=include_comments,
        restrict_breakpoint_types=False,
        breakpoint_types=[],
        restrict_sites=False,
        sites_of_infection=[],
    )


@pytest.mark.parametrize(
    ("include_comments", "intrinsic", "expert"),
    [(False, "R", "R"), (True, "R*", "R!")],
)
def test_interpret_for_display(include_comments, intrinsic, expert):
    config = _config(include_comments)
    assert interpret_for_display(config, "kpn", "AMP_ND10", "25") == intrinsic
    assert interpret_for_display(config, "sau", "FOX_ND30", "15") == expert
    assert interpret_for_display(config, "eco", "AMP_NM", "<=16") == "S?"  # '?' is never stripped


@pytest.mark.parametrize(("include_comments", "expected"), [(False, "R"), (True, "R*")])
def test_api_single_include_comments(include_comments, expected):
    request = SingleInterpretRequest(
        organism_code="kpn",
        whonet_abx_code="AMP",
        measurement="25",
        guidelines=["CLSI"],
        test_method="disk",
        potency="10",
        guideline_year=2026,
        include_comments=include_comments,
    )
    response = _run_single_interpret(request)
    assert [(r.whonet_test, r.interpretation) for r in response.results] == [("AMP_ND10", expected)]
