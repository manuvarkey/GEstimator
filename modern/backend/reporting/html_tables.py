"""Shared escaped HTML tables and internal report page links."""

from dataclasses import dataclass
from html import escape

from .tables import column_widths


@dataclass(frozen=True)
class Heading:
    """A category separator spanning the visible columns."""

    label: str


@dataclass(frozen=True)
class Total:
    """A subtotal row with the same column layout as the preceding rows."""

    values: tuple


@dataclass(frozen=True)
class Anchor:
    """A stable destination embedded in a table cell."""

    target: str
    label: str

    def html(self):
        return f'<span id="{text(self.target)}">{text(self.label)}</span>'


@dataclass(frozen=True)
class PageLink:
    """A printable page number and its continuous HTML fallback."""

    target: str
    screen_label: str
    prefix: str = ""
    suffix: str = ""

    def html(self):
        return (
            f'{text(self.prefix)}<a class="page-link" href="#{text(self.target)}">'
            f"<span>{text(self.screen_label)}</span></a>{text(self.suffix)}"
        )


def text(value):
    """Escape a plain text value at the one HTML output boundary."""
    return escape(str(value), quote=True)


def table(headings, rows, numeric=(), descriptions=(), widths=(), totals=()):
    """Build accessible table markup without interpolating arbitrary attributes."""
    widths = widths or column_widths(headings)
    output = ["<table>"]
    if widths:
        output.append("<colgroup>" + "".join(f'<col style="width:{width}%">' for width in widths) + "</colgroup>")
    output.append("<thead><tr>")
    for index, label in enumerate(headings):
        css = "number" if index in numeric else ""
        output.append(f'<th scope="col" class="{css}">{text(label)}</th>')
    output.append("</tr></thead><tbody>")
    for row in rows:
        if isinstance(row, Heading):
            output.append(
                f'<tr class="table-group"><th scope="rowgroup" colspan="{len(headings)}">{text(row.label)}</th></tr>'
            )
            continue
        css = ' class="total-row"' if isinstance(row, Total) else ""
        output.append(f"<tr{css}>")
        if isinstance(row, Total):
            row = row.values
        for index, value in enumerate(row):
            css = "number" if index in numeric else "description" if index in descriptions else ""
            output.append(
                f'<td class="{css}">{value.html() if isinstance(value, (Anchor, PageLink)) else text(value)}</td>'
            )
        output.append("</tr>")
    output.append("</tbody>")
    if totals:
        output.append("<tfoot>")
        for label, value in totals:
            output.append(
                f'<tr class="total-row"><th scope="row" colspan="{len(headings) - 1}">{text(label)}</th>'
                f'<td class="number">{text(value)}</td></tr>'
            )
        output.append("</tfoot>")
    output.append("</table>")
    return "".join(output)
