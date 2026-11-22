"""Estimation skills served as read-only MCP resources.

Each skill package is a directory under ``data/skills`` named by its skill id.
It holds ``SKILL.md`` and optional supporting Markdown files (for example
``references/masonry.md``). Every file starts with a front matter block:

    ---
    name: <skill id, SKILL.md only>
    description: <one line telling a client when to read the file>
    ---

Adding a package adds its resources; no code changes are needed. URIs are
``gestimator://skills/<id>`` for SKILL.md and
``gestimator://skills/<id>/<relative path>`` for supporting files. Only files
found by the listing scan can be read, so a URI can never name a path outside
the packaged skills. Skills are static files and need no open project.
"""

import logging
from pathlib import Path
import re

ROOT = Path(__file__).parent / "data" / "skills"
SCHEME = "gestimator://skills/"
MIME = "text/markdown"
SKILL_FILE = "SKILL.md"
SEGMENT = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
DOCUMENT = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\.md")
MAX_DEPTH = 3
MAX_BYTES = 256 * 1024
log = logging.getLogger(__name__)


class ResourceNotFound(LookupError):
    def __init__(self, uri):
        super().__init__(f"Resource not found: {uri}")
        self.uri = uri


def front_matter(text):
    """Return (fields, body) for a leading ``---`` block of ``key: value`` lines."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    fields = {}
    for line in text[4:end].splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip():
            fields[key.strip()] = value.strip().strip('"')
    return fields, text[end + 5:]


def title_of(body, fallback):
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def load(path, root):
    """Return a file's text, or None (logged) when it cannot be read as UTF-8."""
    try:
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("file is larger than the resource limit")
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        log.warning("Skipped skill file %s: %s", path.relative_to(root), exc)
        return None


def contained(path, root):
    try:
        return path.resolve(strict=True).is_relative_to(root.resolve(strict=True)) and path.is_file()
    except OSError:
        return False


def entry(uri, name, path, fields, body, priority):
    return dict(uri=uri, name=name, title=title_of(body, name), description=fields["description"],
                mimeType=MIME, size=path.stat().st_size, annotations=dict(audience=["assistant"], priority=priority)), path


def scan(root=ROOT):
    """Map each URI to (resource listing entry, file path), skills first."""
    resources = {}
    if not root.is_dir():
        return resources
    for package in sorted(root.iterdir()):
        skill = package / SKILL_FILE
        if not package.is_dir() or not SEGMENT.fullmatch(package.name) or not contained(skill, root):
            continue
        text = load(skill, root)
        if text is None:
            continue
        fields, body = front_matter(text)
        if fields.get("name") != package.name or not fields.get("description"):
            log.warning("Skipped skill package %s: SKILL.md needs name: %s and a description", package.name, package.name)
            continue
        uri = SCHEME + package.name
        resources[uri] = entry(uri, package.name, skill, fields, body, 1.0)
        for path in sorted(package.rglob("*.md")):
            parts = path.relative_to(package).parts
            if path == skill or len(parts) > MAX_DEPTH or not DOCUMENT.fullmatch(parts[-1]) or not all(SEGMENT.fullmatch(part) for part in parts[:-1]):
                continue
            text = load(path, root) if contained(path, root) else None
            if text is None:
                continue
            fields, body = front_matter(text)
            if not fields.get("description"):
                log.warning("Skipped skill file %s: it needs a description", path.relative_to(root))
                continue
            relative = "/".join(parts)
            uri = SCHEME + package.name + "/" + relative
            resources[uri] = entry(uri, package.name + "/" + relative, path, fields, body, 0.5)
    return resources


def list_resources(root=ROOT):
    return [resource for resource, _path in scan(root).values()]


def read_resource(uri, root=ROOT):
    """Return the MCP ``resources/read`` result for a packaged skill file."""
    if not isinstance(uri, str) or not uri.startswith(SCHEME) or len(uri) > 300:
        raise ResourceNotFound(uri)
    found = scan(root).get(uri)
    if found is None:
        raise ResourceNotFound(uri)
    _resource, path = found
    text = load(path, root) if contained(path, root) else None
    if text is None:
        raise ResourceNotFound(uri)
    return dict(contents=[dict(uri=uri, mimeType=MIME, text=text)])


def catalog(root=ROOT):
    """Skills with their references, for clients that only use tools."""
    skills = {}
    for resource in list_resources(root):
        skill, _, path = resource["uri"][len(SCHEME):].partition("/")
        if not path:
            skills[skill] = dict(skill=skill, title=resource["title"], description=resource["description"], uri=resource["uri"], references=[])
        elif skill in skills:
            skills[skill]["references"].append(dict(path=path, uri=resource["uri"], title=resource["title"], description=resource["description"]))
    return list(skills.values())
