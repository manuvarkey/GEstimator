"""Build the website (gh-pages branch) from the user manual.

Usage: python tools/build_site.py <gh-pages checkout>

Writes manual.html from docs/manual/README.md and copies the manual images
and the application icon into the checkout. index.html and site.css in the
checkout are written by hand. Review the result, then commit and push the gh-pages branch.
"""

import html
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / "docs/manual"


def inline(text):
    codes = []

    def keep(match):
        codes.append(html.escape(match.group(1)))
        return f"\0{len(codes) - 1}\0"
    text = re.sub(r"`([^`]+)`", keep, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}" loading="lazy">', text)

    def link(match):
        label, target = match.group(1), match.group(2)
        if target.startswith("#"):
            return f'<a href="{target}">{label}</a>'
        if target.startswith("http"):
            return f'<a href="{target}" rel="noopener">{label}</a>'
        return f'<a href="https://github.com/manuvarkey/GEstimator/blob/master/docs/manual/{target}">{label}</a>'
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\0(\d+)\0", lambda m: f"<code>{codes[int(m.group(1))]}</code>", text)


def slug(text):
    return re.sub(r"[^a-z0-9 -]", "", text.lower()).strip().replace(" ", "-")


def render(source):
    out, paragraph, list_kind, table = [], [], None, []

    def flush():
        nonlocal paragraph, list_kind, table
        if paragraph:
            out.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph = []
        if list_kind:
            out.append(f"</{list_kind}>")
            list_kind = None
        if table:
            rows = [[cell.strip() for cell in row.strip("|").split("|")] for row in table if not re.fullmatch(r"\|[-| :]+\|", row)]
            head, body = rows[0], rows[1:]
            out.append('<div class="table"><table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>")
            out.extend("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>" for row in body)
            out.append("</tbody></table></div>")
            table = []
    for line in source.splitlines():
        stripped = line.strip()
        heading = re.match(r"(#{1,3}) (.*)", stripped)
        item = re.match(r"(?:[-*]|(\d+)\.) (.*)", stripped)
        image = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)\)", stripped)
        if not stripped:
            flush()
        elif heading:
            flush()
            level, text = len(heading.group(1)), heading.group(2)
            out.append(f'<h{level} id="{slug(text)}">{inline(text)}</h{level}>')
        elif image:
            flush()
            out.append(f'<figure><img src="{image.group(2)}" alt="{html.escape(image.group(1))}" loading="lazy"><figcaption>{html.escape(image.group(1))}</figcaption></figure>')
        elif stripped.startswith("|"):
            if paragraph or list_kind:
                flush()
            table.append(stripped)
        elif item:
            kind = "ol" if item.group(1) else "ul"
            if paragraph or table or (list_kind and list_kind != kind):
                flush()
            if not list_kind:
                out.append(f"<{kind}>")
                list_kind = kind
            out.append("<li>" + inline(item.group(2)) + "</li>")
        else:
            if list_kind:
                flush()
            paragraph.append(stripped)
    flush()
    return "\n".join(out)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="icon" href="images/icon.png">
<link rel="stylesheet" href="site.css">
</head>
<body>
<header class="bar"><div class="wrap">
<a class="brand" href="index.html"><img src="images/icon.png" alt="" width="28" height="28">GEstimator</a>
<nav><a href="index.html#features">Features</a><a href="manual.html">Manual</a><a href="index.html#download">Download</a><a href="https://github.com/manuvarkey/GEstimator">GitHub</a></nav>
</div></header>
<main class="wrap manual">
{body}
</main>
<footer><div class="wrap">GEstimator is free software under the GNU GPL v3 · <a href="https://github.com/manuvarkey/GEstimator">Source code</a> · <a href="https://github.com/manuvarkey/GEstimator/discussions/">Forum</a> · <a href="https://github.com/manuvarkey/GEstimator/issues">Bug tracker</a></div></footer>
</body>
</html>
"""


def main(target):
    target = Path(target)
    body = render((MANUAL / "README.md").read_text(encoding="utf-8"))
    (target / "manual.html").write_text(PAGE.format(title="GEstimator user manual", description="Step-by-step guide to preparing estimates and rate analyses with GEstimator.", body=body), encoding="utf-8")
    images = target / "images"
    images.mkdir(exist_ok=True)
    for path in (MANUAL / "images").glob("*.png"):
        shutil.copy2(path, images / path.name)
    shutil.copy2(ROOT / "modern/src-tauri/icons/128x128.png", images / "icon.png")


if __name__ == "__main__":
    main(sys.argv[1])
