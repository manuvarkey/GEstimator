"""Optional in-process renderer used to compare the executable experiment."""

import base64

from weasyprint import HTML
from weasyprint.urls import URLFetcher, URLFetcherResponse, URLFetchingError


class EmbeddedAssetFetcher(URLFetcher):
    """Deny file/network access; only embedded raster logos are read."""

    def fetch(self, url, headers=None):
        """Return the WeasyPrint 70 response without invoking network handlers."""
        prefixes = ("data:image/png;base64,", "data:image/jpeg;base64,")
        if not url.startswith(prefixes) or len(url) > 2_700_000:
            raise URLFetchingError("Report asset is not an embedded PNG/JPEG")
        header, encoded = url.split(",", 1)
        return URLFetcherResponse(
            url, body=base64.b64decode(encoded, validate=True), headers={"Content-Type": header[5:].split(";")[0]}
        )


embedded_asset = EmbeddedAssetFetcher(fail_on_errors=True)


def render_pdf(html):
    """Render with the prototype's raster-only resource fetcher."""
    return HTML(string=html, url_fetcher=embedded_asset).write_pdf()
