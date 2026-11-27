"""Licensed bundled Iosevka faces, embedded for offline HTML and PDF exports."""

from base64 import b64encode
from functools import lru_cache
from pathlib import Path

from estimator import misc

DEFAULT_FONT = "Iosevka"


@lru_cache(maxsize=1)
def bundled_css():
    """Keep two original faces; browsers/Pango synthesize italic when requested."""
    directory = Path(misc.abs_path("fonts", "iosevka"))
    rules = []
    for name, weight in (("Regular", 400), ("Bold", 700)):
        data = b64encode((directory / f"Iosevka-{name}.woff2").read_bytes()).decode("ascii")
        rules.append(
            f'@font-face {{ font-family:"Iosevka"; font-weight:{weight}; font-style:normal; src:url(data:font/woff2;base64,{data}) format("woff2"); }}'
        )
    return "".join(rules)
