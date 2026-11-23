"""Reuse installed template modules; each caller still creates its own CustomItem."""

import hashlib
import importlib.util
import re
import sys
from functools import lru_cache
from pathlib import Path

from .. import misc


@lru_cache(maxsize=32)
def _load(filename, digest, source):
    spec = importlib.util.spec_from_file_location(Path(filename).stem, filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    # Compile the source just read: timestamp-based .pyc files can be stale after
    # two edits of equal length within the same second.
    exec(compile(source, filename, "exec"), module.__dict__)
    return module


def load_template(plugin):
    """Load a trusted installed template, using its contents as the cache key."""
    # Step 1: project files choose templates by name, never by filesystem path.
    if not isinstance(plugin, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", plugin):
        raise ValueError("Invalid measurement template name")
    directory = Path(misc.abs_path("meas_templates")).resolve()
    candidate = directory / (plugin + ".py")
    path = candidate.resolve()
    if candidate.is_symlink() or path.parent != directory:
        raise ValueError("Measurement template must be an installed file")
    # Step 2: content keys also detect equal-length edits in the same clock tick.
    source = path.read_bytes()
    return _load(str(path), hashlib.sha256(source).hexdigest(), source)
