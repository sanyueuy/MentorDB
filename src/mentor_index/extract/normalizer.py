from __future__ import annotations

import re
from collections import defaultdict

from bs4 import BeautifulSoup

from mentor_index.core.models import FactRecord, ProfileSection, SectionType, SourceRecord, SourceType
from mentor_index.core.utils import normalize_space, slugify

HEADING_TO_SECTION = {
    "个人简介": SectionType.self_intro,
    "导师介绍": SectionType.self_intro,
    "简介": SectionType.self_intro,
    "about": SectionType.self_intro,
    "研究方向": SectionType.research,
    "research": SectionType.research,
    "招生说明": SectionType.admissions,
    "招生要求": SectionType.admissions,
    "招生": SectionType.admissions,
    "recruit": SectionType.admissions,
    "培养方式": SectionType.mentoring,
    "团队": SectionType.mentoring,
    "实验室": SectionType.mentoring,
    "group": SectionType.mentoring,
    "成果": SectionType.achievements,
    "论文": SectionType.achievements,
    "project": SectionType.achievements,
    "联系方式": SectionType.contact,
    "contact": SectionType.contact,
}


def guess_section_type(title: str) -> SectionType:
    lowered = title.strip().lower()
    for keyword, section_type in HEADING_TO_SECTION.items():
        if keyword in lowered:
            return section_type
    return SectionType.other


def extract_sections_from_html(html: str, source_url: str) -> list[ProfileSection]:
    soup = BeautifulSoup(html, "html.parser")
    sections: list[ProfileSection] = []
    heading_tags = soup.select("h1, h2, h3, h4, h5, h6")

    if not heading_tags:
        body_text = normalize_space(soup.get_text("\n"))
        if body_text:
            sections.append(
                ProfileSection(
                    section_type=SectionType.other,
                    title="页面正文",
                    content=body_text,
                    source_url=source_url,
                )
            )
        return sections

    for heading in heading_tags:
        title = normalize_space(heading.get_text(" "))
        content_blocks = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                break
            text = normalize_space(getattr(sibling, "get_text", lambda *_: str(sibling))("\n"))
            if text:
                content_blocks.append(text)
        content = "\n".join(content_blocks).strip()
        if not content:
            continue
        sections.append(
            ProfileSection(
                section_type=guess_section_type(title),
                title=title,
                content=content,
                source_url=source_url,
            )
        )
    return sections


def extract_contacts(text: str, source_url: str) -> list[FactRecord]:
    facts: list[FactRecord] = []
    email_match = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text)
    if email_match:
        facts.append(FactRecord(key="email", value=email_match.group(1), source_url=source_url))
    phone_match = re.search(
        r"(?:电话|手机|Tel|TEL|Phone|联系电话|联系方式)\s*[:：]?\s*((?:\+?\d{1,4}[- ]?)?(?:0\d{2,3}[- ]?\d{7,8}|1\d{10}))",
        text,
    )
    if phone_match:
        facts.append(FactRecord(key="phone", value=phone_match.group(1).strip(), source_url=source_url))
    return facts


def profile_from_extracted(
    *,
    university: str,
    school: str,
    name: str,
    title: str | None,
    homepage_url: str | None,
    lab_url: str | None,
    sources: list[SourceRecord],
    sections: list[ProfileSection],
) -> dict:
    grouped = defaultdict(list)
    for section in sections:
        grouped[section.section_type].append(section.content)

    research_keywords: list[str] = []
    research_blob = "\n".join(grouped[SectionType.research])
    if research_blob:
        research_keywords = [token.strip(" ;，、") for token in re.split(r"[,\n，、;；]+", research_blob) if token.strip()]

    all_text = "\n".join(section.content for section in sections)
    facts = extract_contacts(all_text, homepage_url or sources[0].url)
    metadata = {
        "has_self_intro": bool(grouped[SectionType.self_intro]),
        "has_admissions": bool(grouped[SectionType.admissions]),
        "has_mentoring": bool(grouped[SectionType.mentoring]),
    }
    return {
        "slug": slugify(f"{university}-{school}-{name}"),
        "name": name,
        "university": university,
        "school": school,
        "title": title,
        "email": next((fact.value for fact in facts if fact.key == "email"), None),
        "phone": next((fact.value for fact in facts if fact.key == "phone"), None),
        "homepage_url": homepage_url,
        "lab_url": lab_url,
        "research_keywords": research_keywords[:10],
        "facts": facts,
        "sections": sections,
        "sources": sources,
        "metadata": metadata,
    }
