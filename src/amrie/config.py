"""Interpretation engine configuration.

Port of ``InterpretationConfiguration.cs``. Reads a JSON configuration file into
:class:`InterpretationConfiguration` and provides :func:`default_configuration`
for programmatic use without a file.

JSON key names use PascalCase to match the C# original
(e.g. ``"GuidelineYear"``, ``"HorizontalAntibioticResults"``). They are matched
case-insensitively and mapped to snake_case dataclass fields. Snake_case field
names are also accepted for backwards compatibility. Unknown keys (such as
``"$schema"``) are ignored.

Like the C# ``System.Text.Json`` reader (``CommentHandling.Skip``,
``AllowTrailingCommas``), ``//`` and ``/* */`` comments and trailing commas are
accepted; see :func:`_preprocess_json`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import orjson

from amrie import constants as C
from amrie.breakpoint import Breakpoint, BreakpointTypes, load_breakpoints
from amrie.expert_rule import RuleCodes
from amrie.paths import system_root_path

_log = logging.getLogger(__name__)


@dataclass
class InterpretationConfiguration:
    """All settings that control a single interpretation run.

    Attributes:
        round_half_dilutions: When ``True`` (default), E-test MIC values are
            snapped to the next standard dilution before comparison.
        include_interpretation_comments: When ``False`` (default), ``"*"`` and
            ``"!"`` suffixes are stripped from the output.
        use_intrinsic_resistance_rules: When ``False``, intrinsic resistance
            rules are bypassed and only breakpoints are applied.
        enabled_expert_interpretation_rules: Whitelist of expert rule codes to
            apply; ``None`` enables all rules.
        guideline_year: The breakpoint table year to use.
        prioritized_breakpoint_types: Ordered list of breakpoint type names
            (e.g. ``["Human", "Animal", "ECOFF"]``); ``None`` allows any type.
        prioritized_sites_of_infection: Ordered list of site names;
            :meth:`update_sites_of_infection` fills in any missing default sites.
        disabled_sites_of_infection: Sites to exclude even if they appear in the
            default order.
        horizontal_antibiotic_results: When ``True`` (default), the output file
            appends ``"_INTERP"`` columns beside each measurement column.  When
            ``False``, antibiotics are transposed into three vertical columns.
        user_defined_breakpoints_file: Path to a user-defined breakpoints TSV;
            loaded into :attr:`user_defined_breakpoints` at read time.
        user_defined_breakpoints: Loaded user-defined breakpoints.
    """
    round_half_dilutions: bool = True
    include_interpretation_comments: bool = False
    use_intrinsic_resistance_rules: bool = True
    enabled_expert_interpretation_rules: list[str] | None = None
    guideline_year: int = C.BREAKPOINT_TABLE_REVISION_YEAR
    prioritized_breakpoint_types: list[str] | None = None
    prioritized_sites_of_infection: list[str] | None = None
    disabled_sites_of_infection: list[str] | None = None
    horizontal_antibiotic_results: bool = True
    user_defined_breakpoints_file: str = ""
    user_defined_breakpoints: list[Breakpoint] = field(default_factory=list)

    def update_sites_of_infection(self) -> None:
        """Reconcile the site-of-infection lists against the canonical default order.

        Called automatically by :func:`read_configuration` after loading.

        * Removes any site name not present in ``DEFAULT_ORDER``.
        * Appends any ``DEFAULT_ORDER`` sites not already in the list (and not
          in ``disabled_sites_of_infection``) so that newly introduced sites are
          included automatically in future table revisions.
        """
        if self.prioritized_sites_of_infection is None:
            return

        default_order = C.SitesOfInfection.DEFAULT_ORDER
        self.prioritized_sites_of_infection = [
            s for s in self.prioritized_sites_of_infection if s in default_order
        ]

        if self.disabled_sites_of_infection is not None:
            self.disabled_sites_of_infection = [
                s for s in self.disabled_sites_of_infection if s in default_order
            ]
            self.prioritized_sites_of_infection = self.prioritized_sites_of_infection + [
                s
                for s in default_order
                if s not in self.prioritized_sites_of_infection
                and s not in self.disabled_sites_of_infection
            ]
        else:
            self.prioritized_sites_of_infection = self.prioritized_sites_of_infection + [
                s for s in default_order if s not in self.prioritized_sites_of_infection
            ]


def _filter_config_keys(data: dict) -> dict:
    """Remove comment and disabled keys from the raw JSON dict."""
    return {
        k: v
        for k, v in data.items()
        if not k.startswith("_Comment") and not k.startswith("DISABLED_")
    }


#: JSON (PascalCase) key -> dataclass field name for every setting a file may set.
_JSON_KEY_TO_FIELD: dict[str, str] = {
    "RoundHalfDilutions": "round_half_dilutions",
    "IncludeInterpretationComments": "include_interpretation_comments",
    "UseIntrinsicResistanceRules": "use_intrinsic_resistance_rules",
    "EnabledExpertInterpretationRules": "enabled_expert_interpretation_rules",
    "GuidelineYear": "guideline_year",
    "PrioritizedBreakpointTypes": "prioritized_breakpoint_types",
    "PrioritizedSitesOfInfection": "prioritized_sites_of_infection",
    "DisabledSitesOfInfection": "disabled_sites_of_infection",
    "HorizontalAntibioticResults": "horizontal_antibiotic_results",
    "UserDefinedBreakpointsFile": "user_defined_breakpoints_file",
}

#: Lookup used to resolve a raw JSON key: case-insensitive PascalCase names, plus
#: the snake_case field names (matched case-insensitively too).
_FIELD_BY_KEY: dict[str, str] = {}
for _json_key, _field_name in _JSON_KEY_TO_FIELD.items():
    _FIELD_BY_KEY[_json_key.lower()] = _field_name
    _FIELD_BY_KEY[_field_name.lower()] = _field_name
del _json_key, _field_name

#: Settings whose empty list means "not set" (C# convention).
_EMPTY_LIST_IS_NONE = {
    "enabled_expert_interpretation_rules",
    "prioritized_breakpoint_types",
    "prioritized_sites_of_infection",
    "disabled_sites_of_infection",
}


def _preprocess_json(text: str) -> str:
    """Strip ``//`` and ``/* */`` comments and trailing commas from JSON text.

    Strings are tracked (including backslash escapes), so ``//`` or ``/*`` inside
    a string literal such as a URL is left untouched. A removed comment is
    replaced with a single space so adjacent tokens stay separated. A comma that
    is directly followed (ignoring whitespace and comments) by ``}`` or ``]`` is
    blanked out.
    """
    out: list[str] = []
    last_sig = -1  # index in ``out`` of the last non-whitespace character
    in_string = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string:
            if ch == "\\" and i + 1 < n:
                out.append(text[i : i + 2])
                i += 2
            else:
                out.append(ch)
                if ch == '"':
                    in_string = False
                i += 1
            last_sig = len(out) - 1
            continue
        if ch == '"':
            in_string = True
        elif ch == "/" and text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end == -1 else end
            continue
        elif ch == "/" and text.startswith("/*", i):
            end = text.find("*/", i + 2)
            out.append(" ")
            i = n if end == -1 else end + 2
            continue
        elif ch in "}]" and last_sig >= 0 and out[last_sig] == ",":
            out[last_sig] = " "
        out.append(ch)
        if not ch.isspace():
            last_sig = len(out) - 1
        i += 1
    return "".join(out)


def read_configuration(config_file: str | Path) -> InterpretationConfiguration:
    """Load an :class:`InterpretationConfiguration` from a JSON file.

    The file may contain ``//`` and ``/* */`` comments and trailing commas.
    Key names are matched case-insensitively. Keys that are not settings (for
    example ``"$schema"``) are ignored and logged at DEBUG level only.

    Keys prefixed with ``"_Comment"`` or ``"DISABLED_"`` are silently ignored,
    allowing the config file to carry documentation and temporarily disabled
    settings without breaking parsing.

    Empty lists for ``EnabledExpertInterpretationRules``,
    ``PrioritizedBreakpointTypes``, ``PrioritizedSitesOfInfection``, and
    ``DisabledSitesOfInfection`` are converted to ``None`` to match the C#
    convention of treating empty lists the same as absent fields.

    If ``UserDefinedBreakpointsFile`` is set and the file exists (resolved
    relative to the package root when a relative path is given), the breakpoints
    are loaded and stored in :attr:`~InterpretationConfiguration.user_defined_breakpoints`.

    Args:
        config_file: Path to the JSON configuration file.

    Returns:
        Populated :class:`InterpretationConfiguration` with sites of infection
        reconciled by :meth:`~InterpretationConfiguration.update_sites_of_infection`.
    """
    path = Path(config_file)
    text = path.read_bytes().decode("utf-8-sig")
    raw = orjson.loads(_preprocess_json(text))
    filtered = _filter_config_keys(raw)

    kwargs: dict = {}
    for key, value in filtered.items():
        field_name = _FIELD_BY_KEY.get(key.lower())
        if field_name is None:
            _log.debug("Ignoring unrecognised configuration key %r in %s", key, path)
            continue
        if field_name in _EMPTY_LIST_IS_NONE and value == []:
            value = None
        kwargs[field_name] = value

    config = InterpretationConfiguration(**kwargs)

    udb_file = config.user_defined_breakpoints_file
    if udb_file:
        udb_path = Path(udb_file)
        if not udb_path.is_absolute():
            udb_path = Path(system_root_path()) / udb_file.replace("\\", "/")
        if udb_path.exists():
            config.user_defined_breakpoints = load_breakpoints(udb_path, user_defined=True)

    config.update_sites_of_infection()
    return config


def default_configuration() -> InterpretationConfiguration:
    """Return a sensible default :class:`InterpretationConfiguration`.

    Enables MRS, BLNAR, and ICR expert rules; restricts to Human breakpoints;
    and enables all default sites of infection in the standard priority order.
    Equivalent to ``InterpretationConfiguration.DefaultConfiguration()`` in C#.

    Returns:
        A ready-to-use configuration with comments included in output.
    """
    return InterpretationConfiguration(
        round_half_dilutions=True,
        include_interpretation_comments=True,
        enabled_expert_interpretation_rules=[
            RuleCodes.MRSTAPH,
            RuleCodes.BLNAR,
            RuleCodes.ICR,
        ],
        guideline_year=C.BREAKPOINT_TABLE_REVISION_YEAR,
        prioritized_breakpoint_types=[BreakpointTypes.HUMAN],
        prioritized_sites_of_infection=list(C.SitesOfInfection.DEFAULT_ORDER),
        disabled_sites_of_infection=[],
        user_defined_breakpoints_file="",
    )
