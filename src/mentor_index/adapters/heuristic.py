from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from mentor_index.adapters.base import FacultyAdapter
from mentor_index.core.models import CrawlPolicy, FacultyProfile, FacultySeed, ProfileSection, RawPage, SourceRecord, SourceType
from mentor_index.core.utils import normalize_space, resolve_url, slugify
from mentor_index.crawl.agent import CrawlerAgent
from mentor_index.extract.normalizer import extract_sections_from_html, profile_from_extracted


GENERIC_STOPWORDS = {
    "更多",
    "查看",
    "登录",
    "退出",
    "首页",
    "上一页",
    "下一页",
    "联系我们",
    "contact",
    "login",
    "home",
    "news",
}


@dataclass(frozen=True)
class HeuristicAdapterConfig:
    university: str
    school: str
    listing_url: str
    adapter_name: str = "heuristic_directory"


class HeuristicDirectoryAdapter(FacultyAdapter):
    def __init__(self, config: HeuristicAdapterConfig):
        self.name = config.adapter_name
        self.university = config.university
        self.school = config.school
        self.listing_url = config.listing_url

    def discover_seeds(self) -> list[FacultySeed]:
        return [
            FacultySeed(
                university=self.university,
                school=self.school,
                url=self.listing_url,
                source_type=SourceType.listing,
            )
        ]

    def list_faculty(self, listing_page: RawPage) -> list[FacultySeed]:
        if not listing_page.raw_html:
            return []
        soup = BeautifulSoup(listing_page.raw_html, "html.parser")
        seeds: list[FacultySeed] = []
        seen_urls: set[str] = set()
        base_domain = urlparse(listing_page.url).netloc

        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "").strip()
            if not href or href.startswith(("#", "javascript:")):
                continue
            url = resolve_url(listing_page.url, href)
            parsed = urlparse(url)
            text = normalize_space(anchor.get_text(" ")) or normalize_space(anchor.get("title", ""))
            if not text or text.lower() in GENERIC_STOPWORDS:
                continue
            if len(text) > 30:
                continue
            if parsed.netloc and base_domain and parsed.netloc != base_domain:
                continue
            if not self._looks_like_profile_link(url, text):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            seeds.append(
                FacultySeed(
                    university=self.university,
                    school=self.school,
                    name_hint=text,
                    url=url,
                    source_type=SourceType.homepage,
                    metadata={"listing_url": listing_page.url, "discovery": "heuristic"},
                )
            )
        return seeds

    def fetch_profile_pages(self, faculty_seed: FacultySeed, crawl_policy: CrawlPolicy, fetch_page) -> list[RawPage]:
        return CrawlerAgent(fetch_page).crawl(faculty_seed.url, crawl_policy)

    def extract_entities(self, faculty_seed: FacultySeed, pages: list[RawPage]) -> dict:
        homepage = pages[0]
        name = faculty_seed.name_hint or self._extract_name(homepage)
        title = self._extract_title(homepage)
        sections: list[ProfileSection] = []
        sources = [
            SourceRecord(url=faculty_seed.metadata.get("listing_url", self.listing_url), label="候选列表页", source_type=SourceType.listing),
            SourceRecord(url=homepage.url, label="教师主页", source_type=SourceType.homepage),
        ]
        lab_url = None
        for page in pages:
            if not page.raw_html:
                continue
            page_sections = extract_sections_from_html(page.raw_html, page.url)
            sections.extend(page_sections)
            if page.url != homepage.url:
                source_type = self._guess_source_type(page.url)
                label = "关联页面"
                if source_type == SourceType.lab:
                    label = "课题组/实验室"
                    lab_url = lab_url or page.url
                elif source_type == SourceType.project:
                    label = "项目/代码页面"
                elif source_type == SourceType.paper:
                    label = "论文/成果页面"
                sources.append(SourceRecord(url=page.url, label=label, source_type=source_type))
        if not lab_url:
            for link in homepage.links:
                if self._guess_source_type(link) == SourceType.lab:
                    lab_url = link
                    sources.append(SourceRecord(url=link, label="课题组/实验室", source_type=SourceType.lab))
                    break
        return {
            "university": faculty_seed.university,
            "school": faculty_seed.school,
            "name": name,
            "title": title,
            "homepage_url": homepage.url,
            "lab_url": lab_url,
            "sources": sources,
            "sections": sections,
            "metadata": {
                "discovery": "heuristic",
                "listing_url": faculty_seed.metadata.get("listing_url", self.listing_url),
                "pages_crawled": len(pages),
            },
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
        payload["metadata"].update(extracted.get("metadata", {}))
        payload["slug"] = slugify(f"{extracted['university']}-{extracted['school']}-{extracted['name']}")
        return FacultyProfile(**payload)

    @staticmethod
    def _looks_like_profile_link(url: str, text: str) -> bool:
        lowered = url.lower()
        if any(token in lowered for token in ("teacher", "faculty", "people", "person", "detail", "info", "profile")):
            return True
        if 1 < len(text) <= 8:
            return True
        return False

    @staticmethod
    def _extract_name(page: RawPage) -> str:
        if page.raw_html:
            soup = BeautifulSoup(page.raw_html, "html.parser")
            for selector in ("h1", ".name", ".teacher-name", ".faculty-name"):
                node = soup.select_one(selector)
                if node:
                    text = normalize_space(node.get_text(" "))
                    if text:
                        return text
        return page.title or "未命名导师"

    @staticmethod
    def _extract_title(page: RawPage) -> str | None:
        lines = [normalize_space(line) for line in page.text.split("\n") if normalize_space(line)]
        for line in lines[:20]:
            if any(keyword in line for keyword in ("教授", "副教授", "研究员", "讲师", "工程师", "professor", "associate professor")):
                return line
            if "职称" in line:
                if "：" in line:
                    return line.split("：", 1)[1].strip()
                if ":" in line:
                    return line.split(":", 1)[1].strip()
        return None

    @staticmethod
    def _guess_source_type(url: str) -> SourceType:
        lowered = url.lower()
        if any(token in lowered for token in ("lab", "group", "team", "center", "实验室", "课题组")):
            return SourceType.lab
        if any(token in lowered for token in ("github.com", "project", "code", "demo")):
            return SourceType.project
        if any(token in lowered for token in ("paper", "publication", "doi", "ieeexplore", "arxiv", "dblp")):
            return SourceType.paper
        return SourceType.other
