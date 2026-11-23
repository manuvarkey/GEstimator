"""Check local documentation links, Markdown anchors and current-page discovery."""

import html
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]\n]*\]\((<[^>\n]*>|[^)\n]*)\)")
HTML_LINK = re.compile(r"\b(?:href|src)=[\"']([^\"']+)[\"']", re.IGNORECASE)


def prose(source):
    """Exclude fenced examples from link/heading checks without parsing their code."""
    lines, fence = [], None
    for line in source.splitlines():
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if match:
            marker, rest = match.groups()
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not rest.strip():
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return "\n".join(lines)


def anchors(source):
    """Recognize GitHub-style heading IDs, duplicate suffixes and explicit HTML IDs."""
    source = prose(source)
    result = set(re.findall(r"\b(?:id|name)=[\"']([^\"']+)[\"']", source, re.IGNORECASE))
    counts = Counter()
    for line in source.splitlines():
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?$", line)
        if not match:
            continue
        title = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", match[1])
        title = re.sub(r"<[^>]+>", "", html.unescape(title)).replace("`", "").replace("*", "")
        slug = re.sub(r"[^\w\s-]", "", title.lower()).strip()
        slug = re.sub(r"\s", "-", slug)
        result.add(slug if counts[slug] == 0 else f"{slug}-{counts[slug]}")
        counts[slug] += 1
    return result


def targets(source):
    """Read inline links/images, reference definitions and quoted HTML URLs."""
    source = re.sub(r"`+[^`\n]*`+", "", prose(source))
    for match in MARKDOWN_LINK.finditer(source):
        value = match[1].strip()
        yield value[1:-1] if value.startswith("<") else value.split()[0] if value else ""
    for match in re.finditer(r"^ {0,3}\[[^\]]+\]:\s*(<[^>]+>|\S+)", source, re.MULTILINE):
        yield match[1].strip("<>")
    yield from HTML_LINK.findall(source)


def document_files(root):
    entries = [root / name for name in ("README.md", "AGENTS.md", "modern/README.md", "modern/AGENTS.md")]
    for directory in ("docs", "packaging", "spreadsheets"):
        entries.extend((root / directory).rglob("*.md"))
    return sorted({path for path in entries if path.is_file()})


def check(root):
    """Return actionable errors; never access remote sites or execute examples."""
    documents = document_files(root)
    contents = {path: path.read_text(encoding="utf-8-sig") for path in documents}
    sections = {path: anchors(source) for path, source in contents.items()}
    links, errors = {}, []

    # Step 1: resolve local destinations and verify Markdown fragments.
    for path, source in contents.items():
        links[path] = set()
        for target in targets(source):
            url = urlsplit(html.unescape(target))
            if url.scheme or url.netloc or not target:
                continue
            destination = unquote(url.path)
            resolved = (
                root / destination.lstrip("/")
                if destination.startswith("/")
                else path.parent / destination
                if destination
                else path
            ).resolve()
            label = f"{path.relative_to(root).as_posix()}: {target}"
            if not resolved.is_relative_to(root):
                errors.append(label + " escapes the repository")
            elif not resolved.exists():
                errors.append(label + " has no local target")
            elif resolved.suffix.lower() == ".md":
                links[path].add(resolved)
                fragment = unquote(url.fragment)
                if resolved not in sections:
                    sections[resolved] = anchors(resolved.read_text(encoding="utf-8-sig"))
                if fragment and fragment not in sections[resolved]:
                    errors.append(label + " has no matching section anchor")

    # Step 2: current contracts must be discoverable from the index and link back.
    index = root / "docs/README.md"
    pending, reached = [index], set()
    while pending:
        path = pending.pop()
        if path not in reached:
            reached.add(path)
            pending.extend(links.get(path, set()) - reached)
    current = [*(root / "docs/architecture").rglob("*.md"), *(root / "docs/features").rglob("*.md")]
    if not index.is_file():
        errors.append("docs/README.md is missing")
    for path in current:
        label = path.relative_to(root).as_posix()
        if path not in reached:
            errors.append(label + " is unreachable from docs/README.md")
        if index not in links.get(path, set()):
            errors.append(label + " needs a link back to docs/README.md")
    return documents, errors


def main():
    documents, errors = check(ROOT)
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print(
        f"Documentation checks passed ({len(documents)} Markdown files; local links, anchors and current-page routing)."
    )


if __name__ == "__main__":
    main()
