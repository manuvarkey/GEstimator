"""Deterministic normalization and optional, layered abbreviation expansion."""

import functools
import hashlib
import json
from pathlib import Path
import re
import unicodedata

VERSION = "1"


def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"\b(?:sq\.?\s*mm|mm2)\b", "sq mm", text)
    text = re.sub(r"\b(?:cu\.?\s*m|cum)\b", "cum", text)
    text = re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", " x ", text)
    text = re.sub(r"(\d)\s*(?:amps?|a)\b", r"\1 amp", text)
    text = re.sub(r"\bdia\b\.?", "diameter", text)
    text = re.sub(r"\b(?:nos|no)\b\.?", "number", text)
    return " ".join(text.split())


def extract(text):
    result = []
    for match in re.finditer(r"([A-Za-z][A-Za-z -]{4,100})\s*\(([A-Z][A-Z0-9&-]{1,11})\)", text):
        term = match[2]
        words = re.findall(r"[A-Za-z]+", match[1])
        # Find the shortest suffix whose initials match the abbreviation.
        expansion = " ".join(words[-len(term):])
        for size in range(1, min(len(words), 12) + 1):
            candidate = words[-size:]
            initials = "".join(word[0].upper() for word in candidate if word.lower() not in ("of", "and", "the"))
            if initials == term:
                expansion = " ".join(candidate)
                break
        result.append(dict(term=term, expand=[expansion]))
    return result


@functools.lru_cache(maxsize=8)
def _extract(text):
    return tuple(extract(text))


def entries(text, enrichment=None, user_path=None):
    # Extraction scans every description; unchanged text reuses the result.
    layers = [list(_extract(text))]
    builtin = []
    for path in sorted((Path(__file__).parent / "data" / "dictionary").glob("*.json")):
        builtin.extend(json.loads(path.read_text()))
    layers.extend([builtin, (enrichment or {}).get("dictionary", [])])
    if user_path and Path(user_path).is_file():
        value = json.loads(Path(user_path).read_text())
        layers.append(value if isinstance(value, list) else value.get("dictionary", []))
    merged = {}
    for layer in layers:
        if not isinstance(layer, list):
            continue
        for entry in layer:
            if not isinstance(entry, dict) or not isinstance(entry.get("term"), str):
                continue
            expansions = entry.get("expand", [])
            if not isinstance(expansions, list) or not all(isinstance(v, str) for v in expansions):
                continue
            key = (entry["term"], entry.get("scope", ""))
            if not entry.get("scope"):
                merged = {k: v for k, v in merged.items() if k[0] != entry["term"]}
            merged[key] = dict(entry, expand=expansions)
    return list(merged.values())


_FIELDS = {"civil": r"civil|concrete|masonry|damp|brick|structur", "electrical": r"electric|e&m|wiring|circuit|switch|conduit|cable", "plumbing": r"plumb|sanitar|water|pipe|tap|fitting", "hvac": r"hvac|duct|air condition|ventilat"}


@functools.lru_cache(maxsize=4096)
def _scope(scope):
    return re.compile(_FIELDS.get(scope, re.escape(scope)))


@functools.lru_cache(maxsize=65536)
def _term(term, flags):
    # '&' remains part of an abbreviation: CP must not match CP&OH.
    return re.compile(r"(?<![\w&])" + re.escape(term) + r"(?![\w&])", flags)


@functools.lru_cache(maxsize=65536)
def _expansion(expansion):
    return re.compile(r"(?<!\w)" + re.escape(expansion) + r"(?!\w)", re.IGNORECASE)


def expand(text, dictionary, category="", embedding=False):
    additions = []
    context = (category + " " + text).casefold()
    folded = text.casefold()
    for entry in dictionary:
        term = entry["term"]
        scope = entry.get("scope", "")
        if scope and not _scope(scope).search(context):
            continue
        flags = 0 if entry.get("case", len(term) <= 3) else re.IGNORECASE
        # The substring tests are cheap prefilters; the patterns decide.
        if term.casefold() in folded and _term(term, flags).search(text):
            additions.extend(entry["expand"][:1] if embedding else entry["expand"])
        else:
            for expansion in entry["expand"]:
                if expansion.casefold() in folded and _expansion(expansion).search(text):
                    additions.append(term)
                    break
    return text + " " + " ".join(additions)


def fingerprint(dictionary):
    return hashlib.sha256((VERSION + json.dumps(dictionary, sort_keys=True)).encode()).hexdigest()
