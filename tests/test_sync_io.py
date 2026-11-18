"""Ports of upstream C# IO fixes: SplitLine / ToLine edge cases and delimiter rules."""

import pytest
import typer
from typer.testing import CliRunner

from amrie import constants as C
from amrie.cli import _resolve_delimiter, app
from amrie.io_utils import split_line, to_line

TAB = "\t"


class TestSplitLine:
    def test_simple_fields(self):
        assert split_line("a,b,c", ",") == ["a", "b", "c"]

    def test_no_delimiter_and_no_quote_returns_record_unchanged(self):
        # Early return keeps surrounding whitespace: no strip is applied.
        assert split_line("  abc  ", ",") == ["  abc  "]

    def test_empty_record(self):
        assert split_line("", ",") == [""]

    def test_empty_fields_are_kept(self):
        assert split_line("a,,b", ",") == ["a", "", "b"]

    def test_trailing_delimiter_adds_final_empty_field(self):
        assert split_line("a,b,", ",") == ["a", "b", ""]

    def test_only_delimiter(self):
        assert split_line(",", ",") == ["", ""]

    def test_unquoted_fields_are_stripped(self):
        assert split_line(" a , b ,c ", ",") == ["a", "b", "c"]

    def test_tab_delimiter(self):
        assert split_line(f"a{TAB}b{TAB}c", TAB) == ["a", "b", "c"]

    def test_quoted_delimiter_is_not_split(self):
        assert split_line('"a,b",c', ",") == ["a,b", "c"]

    def test_quoted_tab_delimiter_is_not_split(self):
        assert split_line(f'"a{TAB}b"{TAB}c', TAB) == [f"a{TAB}b", "c"]

    def test_escaped_quotes_inside_quoted_field(self):
        assert split_line('"say ""hi""",x', ",") == ['say "hi"', "x"]

    def test_doubled_quote_only_field(self):
        assert split_line('"a"" b"', ",") == ['a" b']

    def test_whitespace_around_quoted_field_is_skipped(self):
        # Leading whitespace before the opening quote and after the closing quote is dropped.
        assert split_line('  "a , b"  ,c', ",") == ["a , b", "c"]

    def test_quoted_field_kept_verbatim(self):
        # Whitespace inside quotes survives; it is not stripped.
        assert split_line('" padded ",x', ",") == [" padded ", "x"]

    def test_quote_in_middle_of_unquoted_field_is_literal(self):
        assert split_line('a"b,c', ",") == ['a"b', "c"]

    def test_quote_after_text_is_literal_and_field_stripped(self):
        assert split_line('abc "x" ,d', ",") == ['abc "x"', "d"]

    def test_empty_quoted_field(self):
        assert split_line('"",x', ",") == ["", "x"]

    def test_single_empty_quoted_field(self):
        assert split_line('""', ",") == [""]

    def test_quoted_field_without_delimiter(self):
        # Record has quotes but no delimiter: still goes through the state machine.
        assert split_line('"quoted no delimiter"', ",") == ["quoted no delimiter"]

    def test_quote_without_delimiter_stays_literal_in_unquoted_field(self):
        assert split_line('value"only', ",") == ['value"only']

    def test_unterminated_quote_runs_to_end_of_record(self):
        assert split_line('"unterminated,a', ",") == ["unterminated,a"]

    def test_delimiter_not_in_record_but_quote_is(self):
        assert split_line('"x"', "|") == ["x"]

    def test_multi_character_delimiter_raises(self):
        with pytest.raises(ValueError, match="single character"):
            split_line("a,b", ",,")

    def test_empty_delimiter_raises(self):
        with pytest.raises(ValueError, match="single character"):
            split_line("a,b", "")


class TestToLine:
    def test_plain_values_unquoted(self):
        assert to_line(["a", "b", ""], ",") == "a,b,"

    def test_delimiter_in_value_is_quoted(self):
        assert to_line(["a,b", "c"], ",") == '"a,b",c'

    def test_quote_in_value_is_doubled_and_wrapped(self):
        assert to_line(['say "hi"'], ",") == '"say ""hi"""'

    def test_newline_forces_quoting(self):
        assert to_line(["line1\nline2"], TAB) == '"line1\nline2"'

    def test_carriage_return_forces_quoting(self):
        assert to_line(["a\rb"], TAB) == '"a\rb"'

    def test_leading_space_forces_quoting(self):
        assert to_line([" lead"], ",") == '" lead"'

    def test_trailing_space_forces_quoting(self):
        assert to_line(["trail "], ",") == '"trail "'

    def test_leading_tab_forces_quoting(self):
        assert to_line([f"{TAB}x"], ",") == f'"{TAB}x"'

    @pytest.mark.parametrize(
        "values",
        [
            ["a\nb", " lead", 'q"uote', "plain"],
            ["trailing ", "", "x,y", 'mix "q", z'],
            [f"tab{TAB}inside", "\r\n", "  "],
        ],
    )
    def test_round_trip(self, values):
        delimiter = "," if not any(TAB in v for v in values) else TAB
        line = to_line(values, delimiter)
        assert split_line(line, delimiter) == values


class TestDelimiterValidation:
    @pytest.mark.parametrize("delimiter", [TAB, ",", ";", "|"])
    def test_supported_delimiters_pass(self, delimiter):
        C.Delimiters.validate_file_delimiter(delimiter)

    @pytest.mark.parametrize("delimiter", [":", " ", "\x01", "_"])
    def test_unsupported_delimiter_rejected(self, delimiter):
        with pytest.raises(ValueError, match="Unsupported file delimiter"):
            C.Delimiters.validate_file_delimiter(delimiter)

    def test_unsupported_message_names_printable_char_and_code(self):
        with pytest.raises(ValueError) as exc:
            C.Delimiters.validate_file_delimiter(":")
        assert str(exc.value) == (
            "Unsupported file delimiter ':' (U+003A). "
            "Supported delimiters are TAB, comma (,), semicolon (;), and pipe (|)."
        )

    def test_unsupported_control_char_message_uses_code_only(self):
        with pytest.raises(ValueError) as exc:
            C.Delimiters.validate_file_delimiter("\x01")
        assert str(exc.value).startswith("Unsupported file delimiter U+0001.")

    @pytest.mark.parametrize(
        "token, expected",
        [("TAB", TAB), ("tab", TAB), ("Tab", TAB), (",", ","), (";", ";"), ("|", "|")],
    )
    def test_parse_token_accepts_supported(self, token, expected):
        assert C.Delimiters.parse_file_delimiter_token(token) == expected

    @pytest.mark.parametrize("token", ["", "pipe", ",,", "TABX"])
    def test_parse_token_rejects_multi_char_or_empty(self, token):
        with pytest.raises(ValueError, match="provide TAB or exactly one character"):
            C.Delimiters.parse_file_delimiter_token(token)

    @pytest.mark.parametrize("token", [":", " "])
    def test_parse_token_rejects_unsupported_single_char(self, token):
        with pytest.raises(ValueError, match="Unsupported file delimiter"):
            C.Delimiters.parse_file_delimiter_token(token)

    def test_parse_token_none_raises_type_error(self):
        with pytest.raises(TypeError):
            C.Delimiters.parse_file_delimiter_token(None)


class TestCliDelimiterResolution:
    def test_resolve_accepts_tab_token(self):
        assert _resolve_delimiter("TAB") == TAB

    def test_resolve_rejects_bad_value_as_bad_parameter(self):
        with pytest.raises(typer.BadParameter, match="exactly one character"):
            _resolve_delimiter("pipe")

    def test_resolve_rejects_unsupported_char(self):
        with pytest.raises(typer.BadParameter, match="Unsupported file delimiter"):
            _resolve_delimiter(":")

    def test_file_command_reports_clean_usage_error(self, tmp_path):
        result = CliRunner().invoke(
            app,
            [
                "file",
                "--config", str(tmp_path / "cfg.json"),
                "--delimiter", "pipe",
                "--input", str(tmp_path / "in.txt"),
                "--output", str(tmp_path / "out.txt"),
            ],
        )
        assert result.exit_code == 2
        assert "Traceback" not in result.output
        assert "exactly one character" in result.output
