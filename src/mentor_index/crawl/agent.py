from __future__ import annotations

from collections import deque
from io import BytesIO
from pathlib import Path
import re
import time
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from mentor_index.core.config import AppSettings
from mentor_index.core.models import CrawlPolicy, RawPage
from mentor_index.core.utils import domain_of, normalize_space, resolve_url, sha256_text


URL_PATTERN = re.compile(r"https?://[^\s<>'\"\])]+")


class PageFetcher:
    def __init__(self, settings: AppSettings):
        self.settings = settings

    def fetch(self, url: str, depth: int = 0) -> RawPage:
        if url.startswith("fixture://"):
            return self._fetch_fixture(url, depth)
        response = self._get_with_retries(url)
        final_url = str(response.url)
        content_type = response.headers.get("content-type", "text/html").split(";")[0]
        metadata = {"requested_url": url, "final_url": final_url}
        if "pdf" in content_type or final_url.lower().endswith(".pdf"):
            title, text, links, pdf_metadata = self._extract_pdf_metadata(response.content)
            metadata.update(pdf_metadata)
        else:
            text = response.text
            title, links, html_metadata = self._extract_html_metadata(text, final_url)
            metadata.update(html_metadata)
        return RawPage(
            url=url,
            depth=depth,
            status_code=response.status_code,
            content_type=content_type,
            title=title,
            text=normalize_space(BeautifulSoup(text, "html.parser").get_text("\n")),
            raw_html=text if "html" in content_type else None,
            links=links,
            metadata=metadata,
            fingerprint=sha256_text(text),
        )

    def fetch_text(self, url: str) -> str:
        response = self._get_with_retries(url)
        return response.text

    def _get_with_retries(self, url: str) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(
                    follow_redirects=True,
                    timeout=self.settings.request_timeout_seconds,
                    headers={"User-Agent": self.settings.user_agent},
                ) as client:
                    response = client.get(url)
                    response.raise_for_status()
                    return response
            except httpx.HTTPStatusError:
                raise
            except httpx.RequestError as exc:
                last_error = exc
                if attempt == 2:
                    break
                time.sleep(0.8 * (attempt + 1))
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Failed to fetch URL: {url}")

    def extract_links(self, html: str, base_url: str) -> list[str]:
        _, links, _ = self._extract_html_metadata(html, base_url)
        return links

    def _fetch_fixture(self, url: str, depth: int) -> RawPage:
        fixture_root = Path(self.settings.adapter_fixture_dir or "tests/fixtures")
        relative = url.removeprefix("fixture://")
        target = fixture_root / relative
        text = target.read_text(encoding="utf-8")
        title, links, metadata = self._extract_html_metadata(text, url)
        return RawPage(
            url=url,
            depth=depth,
            status_code=200,
            content_type="text/html",
            title=title,
            text=normalize_space(BeautifulSoup(text, "html.parser").get_text("\n")),
            raw_html=text,
            links=links,
            metadata=metadata,
            fingerprint=sha256_text(text),
        )

    @staticmethod
    def _extract_html_metadata(html: str, base_url: str) -> tuple[str | None, list[str], dict]:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else None
        link_records: list[tuple[str, str]] = []
        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            resolved = resolve_url(base_url, href)
            link_records.append((resolved, "anchor"))

        text_blob = soup.get_text("\n")
        for match in URL_PATTERN.findall(text_blob):
            link_records.append((match.rstrip(").,;"), "text"))

        for node in soup.select("button, [role='button'], .btn, .button, .card, .link-card"):
            label = normalize_space(node.get_text(" "))
            if any(keyword in label.lower() for keyword in ("lab", "group", "homepage", "publication", "github", "项目", "课题组", "实验室")):
                href = node.get("data-href") or node.get("data-url") or node.get("onclick", "")
                match = re.search(r"https?://[^\s'\"\\)]+", href)
                if match:
                    link_records.append((match.group(0), "button_text"))

        unique_links: list[str] = []
        seen: set[str] = set()
        discovery_sources: dict[str, list[str]] = {}
        for link, source in link_records:
            normalized = link.strip()
            normalized = normalized.rstrip("#")
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_links.append(normalized)
            discovery_sources.setdefault(normalized, []).append(source)
        return title, unique_links, {"link_discovery_sources": discovery_sources}

    @staticmethod
    def _extract_pdf_metadata(content: bytes) -> tuple[str | None, str, list[str], dict]:
        reader = PdfReader(BytesIO(content))
        text_parts: list[str] = []
        link_records: list[tuple[str, str]] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text:
                text_parts.append(page_text)
                for match in URL_PATTERN.findall(page_text):
                    link_records.append((match.rstrip(").,;"), "pdf_text"))
            annotations = page.get("/Annots") or []
            for annotation in annotations:
                try:
                    obj = annotation.get_object()
                except Exception:
                    continue
                action = obj.get("/A")
                if action and action.get("/URI"):
                    link_records.append((str(action.get("/URI")), "pdf_annotation"))
        unique_links: list[str] = []
        seen: set[str] = set()
        discovery_sources: dict[str, list[str]] = {}
        for link, source in link_records:
            normalized = link.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_links.append(normalized)
            discovery_sources.setdefault(normalized, []).append(source)
        title = reader.metadata.title if reader.metadata else None
        text = "\n".join(part for part in text_parts if part).strip()
        return title, text, unique_links, {"link_discovery_sources": discovery_sources, "pdf_page_count": len(reader.pages)}


class CrawlerAgent:
    def __init__(self, fetcher: PageFetcher):
        self.fetcher = fetcher

    def crawl(self, start_url: str, crawl_policy: CrawlPolicy) -> list[RawPage]:
        queue = deque([(start_url, 0)])
        pages: list[RawPage] = []
        visited: set[str] = set()
        base_domain = domain_of(start_url)
        external_domains: set[str] = set()

        while queue and len(pages) < crawl_policy.max_pages_per_faculty:
            url, depth = queue.popleft()
            if url in visited or depth > crawl_policy.max_depth:
                continue
            visited.add(url)

            page = self.fetcher.fetch(url, depth=depth)
            pages.append(page)

            if "html" not in page.content_type:
                continue

            for link in page.links:
                parsed = urlparse(link)
                if parsed.scheme not in {"http", "https", "fixture"}:
                    continue
                link_domain = domain_of(link)
                is_external = link_domain and link_domain != base_domain
                if is_external and not crawl_policy.allow_external_domains:
                    continue
                if is_external:
                    external_domains.add(link_domain)
                    if len(external_domains) > crawl_policy.max_external_domains:
                        continue
                queue.append((link, depth + 1))

        return pages
