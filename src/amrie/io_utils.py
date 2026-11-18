"""Shared CSV / delimited-text utilities.

Port of the ``IO_Library.SplitLine``, ``IO_Library.ToLine``, and
``IO_Library.GetResourceHeaders`` helpers from ``IO_Library.cs``. These are kept
in a separate module so that both ``io_library`` (user data files) and the
resource-loading modules (``breakpoint``, ``expert_rule``, etc.) can import them
without creating circular dependencies.
"""

from __future__ import annotations

from amrie import constants as C


def get_resource_headers(headers: list[str]) -> dict[str, int]:
    """Build a column-name → index mapping from a list of header strings.

    Args:
        headers: Ordered list of column names, typically obtained from the first
            row of a resource TSV file.

    Returns:
        Dictionary mapping each header name to its zero-based column index.
    """
    return {name: i for i, name in enumerate(headers)}


def split_line(record: str, delimiter: str) -> list[str]:
    """Split a delimited record respecting quoted fields.

    Port of ``IO_Library.SplitLine`` in the C# source. Rules:

    * A record that is empty, or contains neither the delimiter nor a double
      quote, is returned unchanged as a single field.
    * A quote opens a quoted field only when the field so far is whitespace
      only. Inside a quoted field the delimiter is literal, ``""`` is a literal
      quote, and a single quote closes the field.
    * Whitespace after a closing quote is skipped.
    * Unquoted fields are stripped of surrounding whitespace; quoted fields are
      kept verbatim.
    * A quote in the middle of an unquoted field is literal.
    * The final field is always added, so ``"a,"`` yields ``["a", ""]``.

    Args:
        record: The raw text line to split.
        delimiter: A **single** character used as the field separator. Passing a
            multi-character string raises :exc:`ValueError`.

    Returns:
        List of field strings.

    Raises:
        ValueError: If *delimiter* is not exactly one character long.
    """
    if len(delimiter) != 1:
        raise ValueError(f"delimiter must be a single character, got {delimiter!r}")
    if not record or (delimiter not in record and C.QUOTE not in record):
        return [record if record is not None else ""]

    results: list[str] = []
    field: list[str] = []
    in_qualifier = False
    field_was_quoted = False
    after_closing_quote = False

    def add_field() -> None:
        nonlocal field, field_was_quoted, after_closing_quote
        value = "".join(field)
        results.append(value if field_was_quoted else value.strip())
        field = []
        field_was_quoted = False
        after_closing_quote = False

    idx = 0
    length = len(record)
    while idx < length:
        current = record[idx]

        if in_qualifier:
            if current == C.QUOTE:
                if idx + 1 < length and record[idx + 1] == C.QUOTE:
                    field.append(C.QUOTE)
                    idx += 1
                else:
                    in_qualifier = False
                    after_closing_quote = True
            else:
                field.append(current)
        elif current == delimiter:
            add_field()
        elif after_closing_quote and current.isspace():
            pass
        elif current == C.QUOTE and "".join(field).strip() == "":
            field = []
            field_was_quoted = True
            in_qualifier = True
        else:
            after_closing_quote = False
            field.append(current)
        idx += 1

    add_field()
    return results


def to_line(values: list[str], delimiter: str) -> str:
    """Join a list of field values into a single delimited line.

    Port of ``IO_Library.ToLine``. A field is wrapped in double quotes when it
    contains the delimiter, a double quote, a carriage return or line feed, or
    has leading or trailing whitespace. Existing double quotes inside a wrapped
    field are escaped as ``""``. Empty and plain fields are written as-is.

    Args:
        values: Ordered list of field values to join.
        delimiter: Single-character field separator (e.g. ``"\\t"`` or ``","``).

    Returns:
        A single string with fields joined by *delimiter*, ready to be written as
        a line in a delimited output file.
    """
    def format_field(v: str) -> str:
        if not v:
            return v
        if (
            delimiter not in v
            and C.QUOTE not in v
            and "\r" not in v
            and "\n" not in v
            and not v[0].isspace()
            and not v[-1].isspace()
        ):
            return v
        escaped = v.replace(C.QUOTE, C.TWO_QUOTES) if C.QUOTE in v else v
        return f"{C.QUOTE}{escaped}{C.QUOTE}"

    return delimiter.join(format_field(v) for v in values)
