from __future__ import annotations

from bs4 import BeautifulSoup

from mentor_index.adapters.base import FacultyAdapter
from mentor_index.core.models import CrawlPolicy, FacultyProfile, FacultySeed, RawPage, SourceRecord, SourceType
from mentor_index.core.utils import normalize_space, resolve_url
from mentor_index.crawl.agent import CrawlerAgent
from mentor_index.extract.normalizer import extract_sections_from_html, profile_from_extracted


class ZjuControlAdapter(FacultyAdapter):
    name = "zju_control"
    university = "浙江大学"
    school = "控制科学与工程学院"

    def discover_seeds(self) -> list[FacultySeed]:
        return [
            FacultySeed(
                university=self.university,
                school=self.school,
                url="fixture://zju_control/faculty_list.html",
                source_type=SourceType.listing,
            )
        ]

    def list_faculty(self, listing_page: RawPage) -> list[FacultySeed]:
        if not listing_page.raw_html:
            return []
        soup = BeautifulSoup(listing_page.raw_html, "html.parser")
        seeds = []
        for anchor in soup.select("[data-faculty-name][href], a.faculty-link[href]"):
            url = resolve_url(listing_page.url, anchor.get("href"))
            seeds.append(
                FacultySeed(
                    university=self.university,
                    school=self.school,
                    name_hint=anchor.get("data-faculty-name") or normalize_space(anchor.get_text(" ")),
                    url=url,
                    source_type=SourceType.homepage,
                )
            )
        return seeds

    def fetch_profile_pages(
        self,
        faculty_seed: FacultySeed,
        crawl_policy: CrawlPolicy,
        fetch_page,
    ) -> list[RawPage]:
        crawler = CrawlerAgent(fetch_page)
        return crawler.crawl(faculty_seed.url, crawl_policy)

    def extract_entities(self, faculty_seed: FacultySeed, pages: list[RawPage]) -> dict:
        homepage = pages[0]
        name = faculty_seed.name_hint or self._extract_name(homepage)
        title = self._extract_title(homepage)
        sections = []
        sources = [
            SourceRecord(url=homepage.url, label="导师主页", source_type=SourceType.homepage),
        ]
        lab_url = None
        for page in pages:
            if not page.raw_html:
                continue
            page_sections = extract_sections_from_html(page.raw_html, page.url)
            sections.extend(page_sections)
            if page.url != homepage.url:
                sources.append(SourceRecord(url=page.url, label="关联外链", source_type=SourceType.other))
                if not lab_url and any(keyword in page.url.lower() for keyword in ["lab", "group"]):
                    lab_url = page.url
        if not lab_url:
            lab_url = next((link for link in homepage.links if "lab" in link.lower() or "group" in link.lower()), None)
        return {
            "university": faculty_seed.university,
            "school": faculty_seed.school,
            "name": name,
            "title": title,
            "homepage_url": homepage.url,
            "lab_url": lab_url,
            "sources": sources,
            "sections": sections,
        }

    def normalize_profile(self, extracted: dict) -> FacultyProfile:
        payload = profile_from_extracted(
            university=extracted["university"],
            school=extracted["school"],
            name=extracted["name"],
            title=extracted["title"],
            homepage_url=extracted["homepage_url"],
            lab_url=extracted["lab_url"],
            sources=extracted["sources"],
            sections=extracted["sections"],
        )
        return FacultyProfile(**payload)

    @staticmethod
    def _extract_name(page: RawPage) -> str:
        if page.raw_html:
            soup = BeautifulSoup(page.raw_html, "html.parser")
            name = soup.select_one("h1")
            if name:
                return normalize_space(name.get_text(" "))
        return page.title or "未命名导师"

    @staticmethod
    def _extract_title(page: RawPage) -> str | None:
        text = page.text
        for line in text.split("\n"):
            cleaned = normalize_space(line)
            if "职称" in cleaned:
                if "：" in cleaned:
                    return cleaned.split("：", 1)[1].strip()
                if ":" in cleaned:
                    return cleaned.split(":", 1)[1].strip()
        return None
