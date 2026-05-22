"""HTTP scraping with HTML/PDF/JS fallbacks, robots.txt, rate limiting, cache.

We own this layer (not delegated to Anthropic) so we control politeness,
caching, and PDF handling.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib import robotparser
from urllib.parse import urlparse

import httpx

from .confidence import Liveness

log = logging.getLogger(__name__)


# ---------- Cache --------------------------------------------------------


class FileCache:
    """Simple URL -> bytes cache keyed by sha1(url). No expiry — official
    legal texts change at most yearly and we want runs to be cheap to re-run."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, url: str, ext: str = "bin") -> Path:
        h = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return self.root / f"{h}.{ext}"

    def get(self, url: str, ext: str = "bin") -> Optional[bytes]:
        p = self._path(url, ext)
        if p.exists():
            return p.read_bytes()
        return None

    def put(self, url: str, data: bytes, ext: str = "bin") -> Path:
        p = self._path(url, ext)
        p.write_bytes(data)
        return p


# ---------- Fetch result -------------------------------------------------


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    content: bytes
    text: str        # extracted text (HTML -> trafilatura/readability; PDF -> pymupdf; else decoded)
    is_pdf: bool


# ---------- Robots policy -------------------------------------------------


class RobotsPolicy:
    """Per-host robots.txt cache."""

    def __init__(self, user_agent: str, *, enabled: bool = True):
        self.user_agent = user_agent
        self.enabled = enabled
        self._parsers: dict[str, robotparser.RobotFileParser] = {}

    def allowed(self, url: str, http: httpx.Client) -> bool:
        if not self.enabled:
            return True
        host = urlparse(url).netloc
        if not host:
            return True
        rp = self._parsers.get(host)
        if rp is None:
            rp = robotparser.RobotFileParser()
            robots_url = f"{urlparse(url).scheme}://{host}/robots.txt"
            try:
                r = http.get(robots_url, timeout=10.0)
                if r.status_code >= 400:
                    rp.parse([])
                else:
                    rp.parse(r.text.splitlines())
            except Exception:
                # If robots.txt is unreachable, default to allow (common for
                # bare gov sites with no robots.txt).
                rp.parse([])
            self._parsers[host] = rp
        try:
            return rp.can_fetch(self.user_agent, url)
        except Exception:
            return True


# ---------- Scraper ------------------------------------------------------


class HttpScraper:
    """High-level fetcher used by both discovery (probe) and scraping (fetch).

    `probe(url)` is the lightweight liveness probe used during verification
    (returns liveness + a small text sample for title matching).

    `fetch(url)` is the full content fetch used during the SCRAPE phase.
    """

    def __init__(
        self,
        *,
        cache: FileCache,
        user_agent: str,
        timeout: float = 30.0,
        rate_limit_seconds: float = 1.5,
        respect_robots: bool = True,
        playwright_fallback: bool = True,
    ):
        self.cache = cache
        self.user_agent = user_agent
        self.timeout = timeout
        self.rate_limit_seconds = rate_limit_seconds
        self.respect_robots = respect_robots
        self.playwright_fallback = playwright_fallback

        self.robots = RobotsPolicy(user_agent, enabled=respect_robots)
        self._last_request: dict[str, float] = {}

        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.5",
            "Accept-Language": "en;q=0.9,*;q=0.5",
        }
        self.client = httpx.Client(
            headers=headers, follow_redirects=True, timeout=timeout
        )

    # ----- politeness ------------------------------------------------

    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        last = self._last_request.get(host)
        if last is not None:
            wait = self.rate_limit_seconds - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_request[host] = time.time()

    # ----- probe (verification) --------------------------------------

    def probe(self, url: str) -> tuple[Liveness, str]:
        """Lightweight liveness + small text sample for title matching.

        Uses the cache when possible. Never falls back to playwright in
        probe — we only need a header + a few KB.
        """
        try:
            if not self.robots.allowed(url, self.client):
                log.info("probe blocked-by-robots url=%s", url)
                return Liveness(ok=False, status_code=None), ""

            cached = self.cache.get(url, "html")
            if cached is not None:
                sample = _decode_sample(cached)
                return Liveness(ok=True, status_code=200, content_length=len(cached), final_url=url), sample

            self._throttle(url)
            r = self.client.get(url, timeout=self.timeout)
            ok = 200 <= r.status_code < 400
            content = r.content or b""
            ct = (r.headers.get("content-type") or "").lower()

            if ok and content:
                if "pdf" in ct or url.lower().endswith(".pdf"):
                    self.cache.put(url, content, "pdf")
                    try:
                        sample = _pdf_to_text(content)[:8000]
                    except Exception:
                        sample = ""
                else:
                    self.cache.put(url, content, "html")
                    sample = _decode_sample(content)
            else:
                sample = ""

            return (
                Liveness(
                    ok=ok,
                    status_code=r.status_code,
                    content_length=len(content),
                    final_url=str(r.url),
                ),
                sample,
            )
        except (httpx.HTTPError, OSError) as e:
            log.info("probe error url=%s err=%s", url, e)
            return Liveness(ok=False, status_code=None), ""

    # ----- fetch (scrape) --------------------------------------------

    def fetch(self, url: str) -> Optional[FetchResult]:
        if not self.robots.allowed(url, self.client):
            log.info("fetch blocked-by-robots url=%s", url)
            return None

        # Try cache first.
        cached_pdf = self.cache.get(url, "pdf")
        if cached_pdf:
            text = _pdf_to_text(cached_pdf)
            return FetchResult(
                url=url, final_url=url, status_code=200,
                content_type="application/pdf", content=cached_pdf,
                text=text, is_pdf=True,
            )
        cached_html = self.cache.get(url, "html")
        if cached_html:
            text = _html_to_text(cached_html, url)
            return FetchResult(
                url=url, final_url=url, status_code=200,
                content_type="text/html", content=cached_html,
                text=text, is_pdf=False,
            )

        try:
            self._throttle(url)
            r = self.client.get(url)
            content = r.content or b""
            ct = (r.headers.get("content-type") or "").lower()
            is_pdf = "pdf" in ct or url.lower().endswith(".pdf")

            if is_pdf:
                self.cache.put(url, content, "pdf")
                text = _pdf_to_text(content)
            else:
                self.cache.put(url, content, "html")
                text = _html_to_text(content, url)
                # Fall back to playwright for JS-rendered pages with very
                # little extracted text.
                if self.playwright_fallback and len(text.strip()) < 200:
                    pw_text = _playwright_render(url, self.user_agent, self.timeout)
                    if pw_text:
                        text = pw_text

            return FetchResult(
                url=url,
                final_url=str(r.url),
                status_code=r.status_code,
                content_type=ct,
                content=content,
                text=text,
                is_pdf=is_pdf,
            )
        except (httpx.HTTPError, OSError) as e:
            log.warning("fetch error url=%s err=%s", url, e)
            return None

    def close(self) -> None:
        self.client.close()


# ---------- Extractors ---------------------------------------------------


def _decode_sample(b: bytes) -> str:
    # Take just the first ~12 kB — enough to find titles + a bit of body.
    head = b[:12_000]
    for enc in ("utf-8", "latin-1"):
        try:
            return head.decode(enc, errors="ignore")
        except Exception:
            continue
    return ""


def _html_to_text(content: bytes, url: str) -> str:
    """Try trafilatura first (best for legal text), then readability fallback."""
    try:
        import trafilatura  # local import keeps base import cheap

        txt = trafilatura.extract(
            content,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
        if txt and len(txt.strip()) > 100:
            return txt
    except Exception as e:
        log.debug("trafilatura failed url=%s err=%s", url, e)

    # Readability fallback.
    try:
        from readability import Document
        from html import unescape
        import re

        doc = Document(content)
        summary_html = doc.summary(html_partial=True)
        # Crude HTML strip — good enough as a last resort.
        text = re.sub(r"<[^>]+>", " ", summary_html)
        text = unescape(re.sub(r"\s+", " ", text)).strip()
        return text
    except Exception as e:
        log.debug("readability failed url=%s err=%s", url, e)

    # Last resort: best-effort decode.
    try:
        return content.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _pdf_to_text(content: bytes) -> str:
    import pymupdf  # type: ignore

    out: list[str] = []
    with pymupdf.open(stream=content, filetype="pdf") as doc:
        for page in doc:
            out.append(page.get_text("text"))
    return "\n\n".join(out)


def _playwright_render(url: str, user_agent: str, timeout: float) -> str:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as e:
        log.info("playwright not available: %s", e)
        return ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()
            page.goto(url, timeout=int(timeout * 1000), wait_until="domcontentloaded")
            page.wait_for_timeout(1500)  # let JS settle
            text = page.evaluate("() => document.body && document.body.innerText || ''")
            browser.close()
            return text or ""
    except Exception as e:
        log.info("playwright render failed url=%s err=%s", url, e)
        return ""
