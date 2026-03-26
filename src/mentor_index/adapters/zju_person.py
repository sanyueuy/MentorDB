from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup
import httpx
from httpx import HTTPStatusError

from mentor_index.adapters.base import FacultyAdapter
from mentor_index.core.models import CrawlPolicy, FacultyProfile, FacultySeed, ProfileSection, RawPage, SectionType, SourceRecord, SourceType
from mentor_index.core.utils import domain_of, normalize_space, resolve_url, sha256_text, slugify
from mentor_index.crawl.browser import BrowserSearchFetcher
from mentor_index.extract.normalizer import extract_sections_from_html, guess_section_type, profile_from_extracted


PERSON_ROOT = "https://person.zju.edu.cn"
PERSON_SITE_PATH = "https://person.zju.edu.cn/person"


@dataclass(frozen=True)
class ZjuSchoolConfig:
    adapter_name: str
    school_name: str
    listing_url: str


SCHOOL_CONFIGS = {
    "zju_control_real": ZjuSchoolConfig(
        adapter_name="zju_control_real",
        school_name="控制科学与工程学院",
        listing_url="https://person.zju.edu.cn/index/search?companys=537000~%E6%8E%A7%E5%88%B6%E7%A7%91%E5%AD%A6%E4%B8%8E%E5%B7%A5%E7%A8%8B%E5%AD%A6%E9%99%A2",
    ),
    "zju_cs_real": ZjuSchoolConfig(
        adapter_name="zju_cs_real",
        school_name="计算机科学与技术学院",
        listing_url="https://person.zju.edu.cn/index/search?companys=521000~%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A7%91%E5%AD%A6%E4%B8%8E%E6%8A%80%E6%9C%AF%E5%AD%A6%E9%99%A2",
    ),
    "zju_ai_real": ZjuSchoolConfig(
        adapter_name="zju_ai_real",
        school_name="人工智能学院",
        listing_url="https://person.zju.edu.cn/index/search?companys=J00020~%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD%E5%AD%A6%E9%99%A2",
    ),
    "zju_software_real": ZjuSchoolConfig(
        adapter_name="zju_software_real",
        school_name="软件学院",
        listing_url="https://person.zju.edu.cn/index/search?companys=522000~%E8%BD%AF%E4%BB%B6%E5%AD%A6%E9%99%A2",
    ),
}


class ZjuPersonSearchAdapter(FacultyAdapter):
    university = "浙江大学"

    def __init__(self, config: ZjuSchoolConfig):
        self.name = config.adapter_name
        self.school = config.school_name
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

    def fetch_listing_page(self, listing_seed: FacultySeed, fetch_page) -> RawPage:
        if listing_seed.url.startswith("fixture://"):
            return fetch_page.fetch(listing_seed.url)
        return BrowserSearchFetcher(fetch_page.settings).fetch_zju_search_page(listing_seed.url)

    def list_faculty(self, listing_page: RawPage) -> list[FacultySeed]:
        entries = listing_page.metadata.get("entries", [])
        seeds: list[FacultySeed] = []
        for entry in entries:
            mapping_name = entry.get("mapping_name")
            if not mapping_name:
                continue
            profile_url = f"{PERSON_ROOT}/{mapping_name}"
            seeds.append(
                FacultySeed(
                    university=self.university,
                    school=self.school,
                    name_hint=entry.get("cn_name"),
                    url=profile_url,
                    source_type=SourceType.homepage,
                    metadata={
                        "listing_entry": entry,
                        "listing_url": listing_page.url,
                    },
                )
            )
        return seeds

    def fetch_profile_pages(
        self,
        faculty_seed: FacultySeed,
        crawl_policy: CrawlPolicy,
        fetch_page,
    ) -> list[RawPage]:
        homepage = fetch_page.fetch(faculty_seed.url)
        if "person.zju.edu.cn" not in faculty_seed.url:
            return [homepage]

        pages = [homepage]
        tab_pages = self._fetch_person_columns(homepage, fetch_page)
        pages.extend(tab_pages)
        pages.extend(self._fetch_linked_pages(pages, fetch_page, crawl_policy))
        return pages

    def extract_entities(self, faculty_seed: FacultySeed, pages: list[RawPage]) -> dict[str, Any]:
        homepage = pages[0]
        base_info = self._extract_person_base_info(homepage, faculty_seed)
        sections = self._build_sections_from_pages(homepage, pages)
        sources = [
            SourceRecord(url=homepage.url, label="教师个人主页", source_type=SourceType.homepage),
            SourceRecord(
                url=faculty_seed.metadata.get("listing_url", self.listing_url),
                label="学院检索页",
                source_type=SourceType.listing,
            ),
        ]
        if base_info.get("lab_url"):
            sources.append(SourceRecord(url=base_info["lab_url"], label="课题组/实验室", source_type=SourceType.lab))
        known_urls = {source.url for source in sources}
        declared_tabs = homepage.metadata.get("declared_tabs", {})
        for column_id, section_title in declared_tabs.items():
            if column_id == "0":
                tab_url = f"{homepage.url}#column-0"
            else:
                tab_url = f"{homepage.url}#column-{column_id}"
            if tab_url in known_urls:
                continue
            sources.append(
                SourceRecord(
                    url=tab_url,
                    label=section_title,
                    source_type=SourceType.other,
                )
            )
            known_urls.add(tab_url)
        for page in pages[1:]:
            if page.url in known_urls:
                continue
            if page.url.startswith(PERSON_SITE_PATH) and page.metadata.get("section_title") in declared_tabs.values():
                continue
            sources.append(
                SourceRecord(
                    url=page.url,
                    label=page.metadata.get("section_title", "关联页面"),
                    source_type=SourceType.other,
                )
            )
            known_urls.add(page.url)

        extracted = profile_from_extracted(
            university=faculty_seed.university,
            school=faculty_seed.school,
            name=base_info["name"],
            title=base_info["title"],
            homepage_url=homepage.url,
            lab_url=base_info.get("lab_url"),
            sources=sources,
            sections=sections,
        )
        extracted["email"] = base_info.get("email") or extracted["email"]
        extracted["phone"] = base_info.get("phone")
        extracted["metadata"].update(
            {
                "page_uid": homepage.metadata.get("page_uid"),
                "mapping_name": base_info.get("mapping_name"),
                "listing_entry": faculty_seed.metadata.get("listing_entry", {}),
                "address": base_info.get("address"),
                "degree": base_info.get("degree"),
                "school_search_url": faculty_seed.metadata.get("listing_url", self.listing_url),
                "declared_tabs": homepage.metadata.get("declared_tabs", {}),
                "fetched_tab_titles": [page.metadata.get("section_title") for page in pages[1:] if page.metadata.get("section_title")],
            }
        )
        if base_info.get("research_keywords"):
            extracted["research_keywords"] = base_info["research_keywords"]
        return extracted

    def normalize_profile(self, extracted: dict[str, Any]) -> FacultyProfile:
        profile = FacultyProfile(**extracted)
        metadata = extracted.get("metadata", {})
        mapping_name = metadata.get("mapping_name")
        if not mapping_name:
            listing_entry = metadata.get("listing_entry", {})
            mapping_name = listing_entry.get("mapping_name")
        slug_parts = [profile.university, profile.school, profile.name]
        if mapping_name:
            slug_parts.append(str(mapping_name))
        profile.slug = slugify("-".join(slug_parts))
        return profile

    def _fetch_person_columns(self, homepage: RawPage, fetch_page) -> list[RawPage]:
        if not homepage.raw_html:
            return []
        html = homepage.raw_html
        page_uid_match = re.search(r"var pageUid = '([^']+)';", html)
        api_column_match = re.search(r'var apiColumn = "([^"]+)";', html)
        if not page_uid_match or not api_column_match:
            return []

        page_uid = page_uid_match.group(1)
        api_column = api_column_match.group(1)
        homepage.metadata["page_uid"] = page_uid
        tab_titles = self._extract_tab_titles(html)
        homepage.metadata["declared_tabs"] = tab_titles

        tab_pages: list[RawPage] = []
        failed_titles: dict[str, str] = {}
        for column_id, section_title in tab_titles.items():
            endpoint = f"{PERSON_SITE_PATH}{api_column}&column_id={column_id}&pageUid={page_uid}&type=1"
            try:
                payload = fetch_page.fetch_text(endpoint)
            except (HTTPStatusError, httpx.RequestError):
                failed_titles[column_id] = section_title
                continue
            data = self._parse_json_payload(payload)
            if not data:
                failed_titles[column_id] = section_title
                continue
            content_html = data.get("content") or data.get("summary") or ""
            text = normalize_space(BeautifulSoup(content_html, "html.parser").get_text("\n"))
            if not content_html or not text or "正在加载中" in text:
                failed_titles[column_id] = section_title
                continue
            links = fetch_page.extract_links(content_html, endpoint)
            tab_pages.append(
                RawPage(
                    url=endpoint,
                    depth=1,
                    status_code=200,
                    content_type="text/html",
                    title=section_title,
                    text=text,
                    raw_html=content_html,
                    links=links,
                    metadata={"section_title": section_title, "column_id": column_id, "page_uid": page_uid},
                    fingerprint=sha256_text(content_html),
                )
            )

        if failed_titles:
            browser_pages = BrowserSearchFetcher(fetch_page.settings).fetch_zju_person_sections(homepage.url)
            seen_column_ids = {page.metadata.get("column_id") for page in tab_pages}
            for page in browser_pages:
                if page.metadata.get("column_id") in seen_column_ids:
                    continue
                tab_pages.append(page)
                seen_column_ids.add(page.metadata.get("column_id"))

        return tab_pages

    def _fetch_linked_pages(self, pages: list[RawPage], fetch_page, crawl_policy: CrawlPolicy) -> list[RawPage]:
        fetched: list[RawPage] = []
        visited = {page.url for page in pages}
        queue = deque((link, 2) for page in pages for link in page.links)
        base_domain = domain_of(pages[0].url)
        external_domains: set[str] = set()

        while queue and len(fetched) + len(pages) < crawl_policy.max_pages_per_faculty:
            url, depth = queue.popleft()
            if url in visited or depth > crawl_policy.max_depth:
                continue
            visited.add(url)
            link_domain = domain_of(url)
            if link_domain and link_domain != base_domain:
                external_domains.add(link_domain)
                if len(external_domains) > crawl_policy.max_external_domains:
                    continue
            if not self._is_relevant_link(url):
                continue
            try:
                page = fetch_page.fetch(url, depth=depth)
            except Exception:
                continue
            fetched.append(page)
        return fetched

    @staticmethod
    def _is_relevant_link(url: str) -> bool:
        lowered = url.lower()
        if "person.zju.edu.cn" in lowered:
            blocked_keywords = (
                "/index/",
                "/childpages/",
                "/computeddata",
                "/person/personalpage.php",
                "/logout",
            )
            if any(keyword in lowered for keyword in blocked_keywords):
                return False
            return True
        allowed_keywords = (
            "scholar.google",
            "orcid.org",
            "dblp.org",
            "github.com",
            "lab",
            "group",
            "project",
            "publication",
            "paper",
            "research",
        )
        return any(keyword in lowered for keyword in allowed_keywords)

    @staticmethod
    def _extract_tab_titles(html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        tab_titles: dict[str, str] = {}
        for item in soup.select("#tab_nav li[col]"):
            column_id = item.get("col", "").strip()
            title = normalize_space(item.get_text(" "))
            if column_id:
                tab_titles[column_id] = title
        if "0" not in tab_titles:
            tab_titles["0"] = "个人简介"
        return tab_titles

    @staticmethod
    def _parse_json_payload(payload: str) -> dict[str, Any] | None:
        start = payload.find("{")
        if start < 0:
            return None
        try:
            data = json.loads(payload[start:])
        except json.JSONDecodeError:
            return None
        return data.get("data") or None

    def _extract_person_base_info(self, homepage: RawPage, faculty_seed: FacultySeed) -> dict[str, Any]:
        soup = BeautifulSoup(homepage.raw_html or "", "html.parser")
        listing_entry = faculty_seed.metadata.get("listing_entry", {})

        def text(selector: str) -> str | None:
            node = soup.select_one(selector)
            if not node:
                return None
            return normalize_space(node.get_text(" "))

        name = text(".userBaseName") or faculty_seed.name_hint or listing_entry.get("cn_name") or "未命名导师"
        degree = text(".personal_name small")
        title_parts = [normalize_space(node.get_text(" ")) for node in soup.select(".zc span") if normalize_space(node.get_text(" "))]
        title = " | ".join(part for part in title_parts if part != "|") or listing_entry.get("work_title")
        email = None
        phone = None
        address = None
        for label in soup.select(".personal_detail label"):
            label_text = normalize_space(label.get_text(" "))
            value_container = label.find_next_sibling()
            value_text = normalize_space(value_container.get_text(" ")) if value_container else None
            if label_text == "邮箱":
                email = value_text
            elif label_text == "电话":
                phone = value_text
            elif label_text == "地址":
                address = value_text
        research_keywords = [
            normalize_space(item.get_text(" ").replace("·", ""))
            for item in soup.select(".second_research li")
            if normalize_space(item.get_text(" "))
        ]
        lab_url = None
        for anchor in soup.select("a[href]"):
            href = resolve_url(homepage.url, anchor.get("href", ""))
            anchor_text = normalize_space(anchor.get_text(" "))
            if any(keyword in anchor_text for keyword in ["实验室", "课题组", "Lab", "Group"]):
                lab_url = href
                break
        mapping_name = homepage.url.rstrip("/").split("/")[-1]
        return {
            "name": name,
            "degree": degree,
            "title": title,
            "email": email,
            "phone": phone,
            "address": address,
            "research_keywords": research_keywords,
            "lab_url": lab_url,
            "mapping_name": mapping_name,
        }

    def _build_sections_from_pages(self, homepage: RawPage, pages: list[RawPage]) -> list[ProfileSection]:
        sections: list[ProfileSection] = []
        base_info = self._extract_person_base_info(homepage, FacultySeed(university=self.university, school=self.school, url=homepage.url))
        base_lines = [
            f"姓名：{base_info['name']}",
            f"职称与导师身份：{base_info['title'] or '未公开'}",
            f"学位：{base_info['degree'] or '未公开'}",
            f"邮箱：{base_info['email'] or '未公开'}",
            f"电话：{base_info['phone'] or '未公开'}",
            f"地址：{base_info['address'] or '未公开'}",
            f"研究方向：{'、'.join(base_info['research_keywords']) or '未公开'}",
        ]
        sections.append(
            ProfileSection(
                section_type=SectionType.basic,
                title="基础信息",
                content="\n".join(base_lines),
                source_url=homepage.url,
            )
        )
        homepage_intro = self._extract_homepage_intro(homepage)
        seen_contents = {normalize_space(sections[0].content)}
        if homepage_intro:
            sections.append(homepage_intro)
            seen_contents.add(normalize_space(homepage_intro.content))

        for page in pages[1:]:
            section_title = page.metadata.get("section_title")
            if section_title and page.raw_html:
                if section_title == "基础信息":
                    continue
                page_text = normalize_space(BeautifulSoup(page.raw_html, "html.parser").get_text("\n"))
                if not page_text or "正在加载中" in page_text:
                    continue
                if page_text in seen_contents:
                    continue
                section_type = guess_section_type(section_title)
                if "教学" in section_title:
                    section_type = SectionType.mentoring
                if "成果" in section_title:
                    section_type = SectionType.achievements
                section = ProfileSection(
                    section_type=section_type,
                    title=section_title,
                    content=page_text,
                    source_url=page.url,
                )
                sections.append(section)
                seen_contents.add(page_text)
            elif page.raw_html:
                for section in extract_sections_from_html(page.raw_html, page.url):
                    if section.title == "基础信息":
                        continue
                    normalized = normalize_space(section.content)
                    if not normalized or normalized in seen_contents:
                        continue
                    sections.append(section)
                    seen_contents.add(normalized)

        if not any(section.section_type == SectionType.research for section in sections) and base_info["research_keywords"]:
            sections.append(
                ProfileSection(
                    section_type=SectionType.research,
                    title="研究方向",
                    content="、".join(base_info["research_keywords"]),
                    source_url=homepage.url,
                )
            )
        unfetched_notes = self._build_unfetched_tab_note(homepage, sections)
        if unfetched_notes:
            sections.append(unfetched_notes)
        if base_info["email"] or base_info["phone"] or base_info["address"]:
            sections.append(
                ProfileSection(
                    section_type=SectionType.contact,
                    title="联系方式",
                    content="\n".join(
                        [
                            f"邮箱：{base_info['email'] or '未公开'}",
                            f"电话：{base_info['phone'] or '未公开'}",
                            f"地址：{base_info['address'] or '未公开'}",
                        ]
                    ),
                    source_url=homepage.url,
                )
            )
        return sections

    @staticmethod
    def _extract_homepage_intro(homepage: RawPage) -> ProfileSection | None:
        if not homepage.raw_html:
            return None
        soup = BeautifulSoup(homepage.raw_html, "html.parser")
        content_node = soup.select_one(".jbxx")
        if not content_node:
            return None
        content = normalize_space(content_node.get_text("\n"))
        if not content or "正在加载中" in content:
            return None
        return ProfileSection(
            section_type=SectionType.self_intro,
            title="个人简介",
            content=content,
            source_url=f"{homepage.url}#column-0",
        )

    def _build_unfetched_tab_note(self, homepage: RawPage, sections: list[ProfileSection]) -> ProfileSection | None:
        declared_tabs = homepage.metadata.get("declared_tabs", {})
        if not declared_tabs:
            return None
        fetched_titles = {section.title for section in sections}
        missing_lines: list[str] = []
        for column_id, title in declared_tabs.items():
            if title in fetched_titles:
                continue
            section_type = guess_section_type(title)
            if section_type == SectionType.other and "招生" not in title and "研究生" not in title:
                continue
            tab_url = f"{homepage.url}#column-0" if column_id == "0" else f"{homepage.url}#column-{column_id}"
            missing_lines.append(f"{title}：站点动态接口当前未返回正文，请人工查看 {tab_url}")
        if not missing_lines:
            return None
        return ProfileSection(
            section_type=SectionType.source_note,
            title="动态栏目提示",
            content="\n".join(missing_lines),
            source_url=homepage.url,
        )
