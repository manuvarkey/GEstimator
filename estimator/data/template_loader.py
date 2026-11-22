"""Reuse installed template modules; each caller still creates its own CustomItem."""

import hashlib
import importlib.util
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
    # Key the cache on the content, not on mtime and size: two equal-length
    # writes within one filesystem timestamp tick leave both unchanged.
    path = Path(misc.abs_path('meas_templates', plugin + '.py')).resolve()
    source = path.read_bytes()
    return _load(str(path), hashlib.sha256(source).hexdigest(), source)
