"""Validate embedded logos used by offline report renderers."""

import base64
import binascii
import re
from xml.etree import ElementTree

MAX_BYTES = 384 * 1024
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"
SVG_ELEMENTS = set(
    """
svg g defs title desc path rect circle ellipse line polyline polygon text tspan
linearGradient radialGradient stop clipPath mask pattern symbol style
""".split()
)
LOCAL_REFERENCE = re.compile(r"#[A-Za-z0-9_.:-]+")
URL = re.compile(r"url\s*\(\s*['\"]?(#[A-Za-z0-9_.:-]+)['\"]?\s*\)", re.I)


def _safe_svg(data):
    """Allow static SVG artwork with local paint references and no external loads."""
    source = data.decode("utf-8-sig")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)|<\?(?!xml\s)", source, re.I):
        return False
    root = ElementTree.fromstring(source)
    if root.tag != SVG_NAMESPACE + "svg":
        return False
    for index, node in enumerate(root.iter()):
        tag = node.tag.removeprefix(SVG_NAMESPACE)
        if index >= 4000 or tag not in SVG_ELEMENTS:
            return False
        for key, value in node.attrib.items():
            name = key.rsplit("}", 1)[-1].lower()
            if (
                name.startswith("on")
                or name == "base"
                or name in ("src", "href")
                and not LOCAL_REFERENCE.fullmatch(value)
            ):
                return False
            if name == "style" or "url" in value.lower():
                if re.search(r"@|\\|url", URL.sub("", value), re.I):
                    return False
        if tag == "style" and re.search(r"@|\\|url", URL.sub("", node.text or ""), re.I):
            return False
    return True


def logo_data(value):
    """Accept a small PNG, JPEG, GIF, WebP or static SVG data URL."""
    if value == "":
        return value
    if not isinstance(value, str) or len(value) > MAX_BYTES * 4 // 3 + 64:
        raise ValueError("Choose a report logo up to 384 KiB")
    prefix, separator, encoded = value.partition(",")
    signatures = {
        "data:image/png;base64": b"\x89PNG\r\n\x1a\n",
        "data:image/jpeg;base64": b"\xff\xd8\xff",
        "data:image/gif;base64": (b"GIF87a", b"GIF89a"),
        "data:image/webp;base64": b"RIFF",
    }
    try:
        data = base64.b64decode(encoded, validate=True)
        if separator and 0 < len(data) <= MAX_BYTES:
            if prefix == "data:image/svg+xml;base64" and _safe_svg(data):
                return value
            if prefix in signatures and data.startswith(signatures[prefix]):
                if prefix != "data:image/webp;base64" or data[8:12] == b"WEBP":
                    return value
    except (binascii.Error, UnicodeError, ElementTree.ParseError):
        pass
    raise ValueError("Choose a valid PNG, JPEG, GIF, WebP or static SVG report logo")
