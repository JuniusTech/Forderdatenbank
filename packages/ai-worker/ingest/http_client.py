import requests
import urllib3

from ingest.pdf_text import is_pdf_url, pdf_bytes_to_html

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


class HttpClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def get(self, url: str, timeout: float = 60.0) -> tuple[int, str, str]:
        try:
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
        except requests.exceptions.SSLError:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = self.session.get(
                url, timeout=timeout, allow_redirects=True, verify=False
            )
        ctype = (response.headers.get("content-type") or "").lower()
        content = response.content or b""
        if (
            "pdf" in ctype
            or is_pdf_url(response.url)
            or is_pdf_url(url)
            or content[:5] == b"%PDF-"
        ):
            html = pdf_bytes_to_html(content, source_url=response.url)
            return response.status_code, response.url, html
        return response.status_code, response.url, response.text
