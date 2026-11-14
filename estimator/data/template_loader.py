"""Reuse installed template modules; each caller still creates its own CustomItem."""

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from .. import misc


@lru_cache(maxsize=32)
def _load(filename, modified, size):
    spec = importlib.util.spec_from_file_location(Path(filename).stem, filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    # Read changed source directly: timestamp-based .pyc files can be stale after
    # two edits of equal length within the same second.
    exec(compile(Path(filename).read_bytes(), filename, "exec"), module.__dict__)
    return module


def load_template(plugin):
    path = Path(misc.abs_path('meas_templates', plugin + '.py')).resolve()
    stat = path.stat()
    return _load(str(path), stat.st_mtime_ns, stat.st_size)
