"""Discover estimation libraries and publish a read-only MCP resource snapshot."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import appdirs

from estimator import misc

ROOT = Path(__file__).parent / "data" / "skills"
SCHEME = "gestimator://skills/"
MIME = "text/markdown"
DEFAULT_LIBRARY = "generic"
SHARED_LIBRARY = "shared"
SEGMENT = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_DEPTH = 3
MAX_BYTES = 256 * 1024
MAX_URI = 300
MANIFEST = "library.json"


class ResourceNotFound(LookupError):
    def __init__(self, uri):
        super().__init__(f"Resource not found: {uri}")
        self.uri = uri


def user_directory():
    """Keep user libraries in application data across program upgrades."""
    return Path(appdirs.user_data_dir(misc.PROGRAM_NAME, misc.PROGRAM_AUTHOR)) / "mcp" / "skills"


def valid_id(value):
    """Recognize an identifier that fits safely in a library URI."""
    return isinstance(value, str) and len(value) <= 64 and SEGMENT.fullmatch(value) is not None


def validate_library_id(value):
    if not valid_id(value):
        raise ValueError("Use a lowercase estimation skill library ID")
    return value


def _front_matter(text):
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
    return fields, text[end + 5 :]


def _read_file(path, root):
    """Read a bounded file from its package. Paths from MCP never reach here."""
    if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise ValueError("File must be inside its package and cannot be a symbolic link")
    if not path.is_file():
        raise ValueError("Expected a regular file")
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("File exceeds the 256 KiB limit")
    return data.decode("utf-8").replace("\r\n", "\n")


@dataclass(frozen=True)
class SkillDocument:
    """Markdown and its listing metadata, captured together at refresh."""

    metadata: dict
    text: str


@dataclass(frozen=True)
class SkillLibrary:
    identity: str
    name: str
    description: str
    bundled: bool
    documents: dict[str, SkillDocument]

    def summary(self):
        return dict(id=self.identity, name=self.name, description=self.description, bundled=self.bundled)


def _load_library(folder, bundled, issues):
    """Validate a manifest, then load each skill and its references."""
    if folder.is_symlink():
        raise ValueError("Library folder cannot be a symbolic link")
    try:
        manifest = json.loads(_read_file(folder / MANIFEST, folder))
    except RecursionError as error:
        raise ValueError("library.json is nested too deeply") from error
    if (
        not isinstance(manifest, dict)
        or type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 1
    ):
        raise ValueError("library.json must declare schema_version 1")
    identity = validate_library_id(manifest.get("id"))
    name, description = manifest.get("name"), manifest.get("description", "")
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ValueError("library.json needs a name of up to 120 characters")
    if not isinstance(description, str) or len(description) > 400:
        raise ValueError("library.json description must be at most 400 characters")

    documents = {}
    for package in sorted(folder.iterdir()):
        try:
            if package.name.startswith(".") or not (package.is_dir() or package.is_symlink()):
                continue
            if package.is_symlink() or not valid_id(package.name):
                raise ValueError("Use a regular skill folder with a lowercase skill ID")
            _load_package(identity, package, documents, issues)
        except (OSError, ValueError) as error:
            issues.append(f"{folder.name}/{package.name}: {error}")
    if not documents:
        raise ValueError("Library has no readable skill packages")
    return SkillLibrary(identity, name.strip(), description.strip(), bundled, documents)


def _load_package(library, package, documents, issues):
    """Publish references only after validating the package's SKILL.md."""
    prefix = SCHEME + library + "/" + package.name
    source = package / "SKILL.md"
    _add_document(documents, prefix, package.name, source, package, main=True)
    for path in sorted(package.rglob("*.md")):
        if path == source or path.suffix != ".md":
            continue
        parts = path.relative_to(package).parts
        if len(parts) > MAX_DEPTH or not valid_id(path.stem) or not all(valid_id(part) for part in parts[:-1]):
            continue
        relative = "/".join(parts)
        try:
            _add_document(documents, prefix + "/" + relative, package.name + "/" + relative, path, package)
        except (OSError, ValueError) as error:
            issues.append(f"{library}/{package.name}/{relative}: {error}")


def _add_document(documents, uri, name, path, package, *, main=False):
    if len(uri) > MAX_URI:
        raise ValueError("Skill URI is too long")
    text = _read_file(path, package)
    fields, body = _front_matter(text)
    if not fields.get("description") or (main and fields.get("name") != name):
        raise ValueError("Skills need a description and SKILL.md must name its package")
    title = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), name)
    metadata = dict(
        uri=uri,
        name=name,
        title=title,
        description=fields["description"],
        mimeType=MIME,
        size=len(text.encode("utf-8")),
        annotations=dict(audience=["assistant"], priority=1.0 if main else 0.5),
    )
    documents[uri] = SkillDocument(metadata, text)


@dataclass(frozen=True)
class SkillCatalog:
    """One selection snapshot used by both protocol resources and tool reads."""

    library_id: str
    documents: dict[str, SkillDocument]

    def list_resources(self):
        return [document.metadata for document in self.documents.values()]

    def read_resource(self, uri):
        if not isinstance(uri, str) or len(uri) > MAX_URI or uri not in self.documents:
            raise ResourceNotFound(uri)
        return dict(contents=[dict(uri=uri, mimeType=MIME, text=self.documents[uri].text)])

    def skills(self):
        """Describe skills and their references for text-only MCP clients."""
        catalog = {}
        for resource in self.list_resources():
            library, skill, *parts = resource["uri"][len(SCHEME) :].split("/")
            key = f"{library}/{skill}"
            entry = {field: resource[field] for field in ("uri", "title", "description")}
            if parts:
                catalog[key]["references"].append(dict(entry, path="/".join(parts)))
            else:
                catalog[key] = dict(entry, skill=skill, library=library, references=[])
        return list(catalog.values())


class SkillLibraries:
    """Own application-level discovery and selection without querying any project."""

    def __init__(self, packaged=ROOT, user=None):
        self.packaged = packaged
        self.user = user_directory() if user is None else user
        self.requested = DEFAULT_LIBRARY
        self.refresh()

    def refresh(self):
        """Build the full replacement before publishing it to MCP readers."""
        libraries, issues = {}, []
        for root, bundled in ((self.packaged, True), (self.user, False)):
            try:
                folders = sorted(root.iterdir())
            except FileNotFoundError:
                if bundled:
                    issues.append("Packaged skill library folder is unavailable")
                continue
            except OSError as error:
                issues.append(f"Cannot scan skill libraries in {root}: {error}")
                continue
            for folder in folders:
                try:
                    if folder.name.startswith(".") or not (folder.is_dir() or folder.is_symlink()):
                        continue
                    library = _load_library(folder, bundled, issues)
                    if library.identity in libraries or (
                        not bundled and library.identity in (DEFAULT_LIBRARY, SHARED_LIBRARY)
                    ):
                        raise ValueError(f"Duplicate or reserved library ID '{library.identity}'")
                    libraries[library.identity] = library
                except (OSError, ValueError) as error:
                    issues.append(f"{folder.name}: {error}")
        self._libraries, self._issues = libraries, issues
        self._publish()
        return self.status()

    def select(self, identity):
        identity = validate_library_id(identity)
        if identity == SHARED_LIBRARY:
            raise ValueError("Choose a selectable estimation skill library")
        self.requested = identity
        self._publish()

    def _publish(self):
        active_id = self.requested if self.requested in self._libraries else DEFAULT_LIBRARY
        documents = {}
        for identity in (active_id, SHARED_LIBRARY):
            if identity in self._libraries:
                documents.update(self._libraries[identity].documents)
        # Replacing the object keeps each HTTP request on a single snapshot.
        self.active = SkillCatalog(active_id, documents)

    def status(self):
        return dict(
            libraries=[
                library.summary() for identity, library in self._libraries.items() if identity != SHARED_LIBRARY
            ],
            active_library=self.active.library_id,
            requested_library=self.requested,
            user_directory=str(self.user),
            issues=self._issues,
        )

    def open_directory(self):
        """Create the application-data folder before the desktop opens it."""
        self.user.mkdir(parents=True, exist_ok=True)
        return str(self.user)
