# Iosevka report font

Unmodified Iosevka Regular and Bold from upstream v34.9.2, converted losslessly
from TTF to WOFF2 with fontTools. The WOFF2 files use Brotli compression
without table transforms so WeasyPrint can load them without reconstructing
the glyph outlines on each export. To regenerate either face from the upstream
TTF, call `fontTools.ttLib.woff2.compress(input_path, output_path, transform_tables=[])`.
Licensed under SIL OFL 1.1 (see OFL.md).

Source: https://github.com/be5invis/Iosevka/releases/tag/v34.9.2
Archive: PkgTTF-Iosevka-34.9.2.zip
SHA-256: 76620515a293be7f7ea389d2e95c7d88c8ff3bebeb32222a8390867f338ac37a

Both faces are bundled by the Python sidecar and embedded as data URLs in default
HTML/PDF reports. Italic running text is synthesized. Excel records the family
name; its viewer needs Iosevka installed to use the same face.
