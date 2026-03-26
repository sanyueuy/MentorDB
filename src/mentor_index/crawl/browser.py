from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup

from mentor_index.core.config import AppSettings
from mentor_index.core.models import RawPage
from mentor_index.core.utils import normalize_space, sha256_text


class BrowserSearchFetcher:
    def __init__(self, settings: AppSettings):
        self.settings = settings

    def fetch_zju_search_page(self, url: str) -> RawPage:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Dynamic ZJU search pages require Playwright. Install with `pip install '.[browser]'`."
            ) from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel=self.settings.browser_channel,
                headless=self.settings.browser_headless,
            )
            page = browser.new_page()
            page.goto(url, wait_until="commit", timeout=self.settings.browser_timeout_ms)
            page.wait_for_timeout(self.settings.browser_wait_after_load_ms)
            try:
                page.wait_for_function(
                    """() => {
                      const app = document.querySelector('#app');
                      const vue = app && app.__vue__;
                      if (!vue || !vue.$store) return false;
                      const list = vue.$store.state.searchAdvancedList || [];
                      return list.length > 0 || (vue.$store.state.totalElements_ || 0) > 0;
                    }""",
                    timeout=min(self.settings.browser_timeout_ms, 20000),
                )
            except PlaywrightTimeoutError:
                page.wait_for_timeout(3000)

            previous_size = -1
            entries: list[dict[str, Any]] = []
            total = 0

            for _ in range(self.settings.browser_expand_max_clicks + 1):
                state = page.evaluate(
                    """() => {
                      const app = document.querySelector('#app');
                      const vue = app && app.__vue__;
                      if (!vue || !vue.$store) return { entries: [], size: 0, total: 0 };
                      const list = vue.$store.state.searchAdvancedList || [];
                      return {
                        entries: list,
                        size: list.length,
                        total: vue.$store.state.totalElements_ || list.length
                      };
                    }"""
                )
                entries = state["entries"]
                total = state["total"] or len(entries)
                if len(entries) >= total:
                    break
                if len(entries) == previous_size:
                    break
                previous_size = len(entries)

                more_button = page.locator("text=查看更多")
                if more_button.count() == 0:
                    break
                more_button.first.click(timeout=5000)
                try:
                    page.wait_for_function(
                        """(lastSize) => {
                          const app = document.querySelector('#app');
                          const vue = app && app.__vue__;
                          if (!vue || !vue.$store) return false;
                          return (vue.$store.state.searchAdvancedList || []).length > lastSize;
                        }""",
                        arg=len(entries),
                        timeout=10000,
                    )
                except PlaywrightTimeoutError:
                    page.wait_for_timeout(1500)

            html = page.content()
            browser.close()

        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entry in entries:
            key = str(entry.get("id") or entry.get("mapping_name") or entry.get("cn_name"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)

        soup = BeautifulSoup(html, "html.parser")
        text = normalize_space(soup.get_text("\n"))
        return RawPage(
            url=url,
            depth=0,
            status_code=200,
            content_type="text/html",
            title=soup.title.get_text(strip=True) if soup.title else None,
            text=text,
            raw_html=html,
            links=[],
            metadata={"entries": deduped, "total": total, "source": "browser"},
            fingerprint=sha256_text(html + str(total) + str(len(deduped))),
        )

    def fetch_zju_person_sections(self, url: str) -> list[RawPage]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Dynamic ZJU profile pages require Playwright. Install with `pip install '.[browser]'`."
            ) from exc

        pages: list[RawPage] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel=self.settings.browser_channel,
                headless=self.settings.browser_headless,
            )
            page = browser.new_page()
            page.goto(url, wait_until="commit", timeout=self.settings.browser_timeout_ms)
            page.wait_for_timeout(self.settings.browser_wait_after_load_ms)
            page.wait_for_function(
                """() => {
                  return !!(window.columnData && document.querySelector('#tab_nav li[col]'));
                }""",
                timeout=min(self.settings.browser_timeout_ms, 20000),
            )
            tab_entries = page.evaluate(
                """() => {
                  return Array.from(document.querySelectorAll('#tab_nav li[col]')).map((item) => ({
                    column_id: item.getAttribute('col'),
                    title: (item.textContent || '').trim()
                  }));
                }"""
            )
            seen_fingerprints: set[str] = set()
            for entry in tab_entries:
                response_text = None
                status_code = None
                try:
                    with page.expect_response(
                        lambda response: "/api/column?" in response.url and f"column_id={entry['column_id']}" in response.url,
                        timeout=10000,
                    ) as response_info:
                        page.locator(f"#tab_nav li[col='{entry['column_id']}'] a").click(timeout=5000)
                    response = response_info.value
                    status_code = response.status
                    if response.ok:
                        response_text = response.text()
                except PlaywrightTimeoutError:
                    continue

                content_html = ""
                if response_text:
                    try:
                        payload = json.loads(response_text)
                        content_html = (payload.get("data") or {}).get("content") or ""
                    except json.JSONDecodeError:
                        content_html = ""
                if not content_html:
                    continue

                text = normalize_space(BeautifulSoup(content_html, "html.parser").get_text("\n"))
                if not text or "正在加载中" in text:
                    continue

                fingerprint = sha256_text(content_html)
                if fingerprint in seen_fingerprints:
                    continue
                seen_fingerprints.add(fingerprint)

                links = self._extract_links_from_html(content_html, url)
                pages.append(
                    RawPage(
                        url=f"{url}#column-{entry['column_id']}",
                        depth=1,
                        status_code=status_code or 200,
                        content_type="text/html",
                        title=entry["title"],
                        text=text,
                        raw_html=content_html,
                        links=links,
                        metadata={"section_title": entry["title"], "column_id": entry["column_id"], "source": "browser"},
                        fingerprint=fingerprint,
                    )
                )
            browser.close()
        return pages

    @staticmethod
    def _extract_links_from_html(html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            if href.startswith(("http://", "https://")):
                links.append(href)
            else:
                from mentor_index.core.utils import resolve_url

                links.append(resolve_url(base_url, href))
        return links
