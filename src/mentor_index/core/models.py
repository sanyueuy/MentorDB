from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceType(str, Enum):
    listing = "listing"
    homepage = "homepage"
    lab = "lab"
    pdf = "pdf"
    paper = "paper"
    project = "project"
    other = "other"


class SectionType(str, Enum):
    basic = "basic"
    self_intro = "self_intro"
    research = "research"
    admissions = "admissions"
    mentoring = "mentoring"
    achievements = "achievements"
    links = "links"
    contact = "contact"
    source_note = "source_note"
    other = "other"


class FacultySeed(BaseModel):
    university: str
    school: str
    name_hint: str | None = None
    url: str
    source_type: SourceType = SourceType.listing
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrawlPolicy(BaseModel):
    max_depth: int = 2
    max_pages_per_faculty: int = 12
    max_external_domains: int = 8
    allow_external_domains: bool = True
    allowed_content_types: tuple[str, ...] = (
        "text/html",
        "application/pdf",
        "text/plain",
    )


class SourceRecord(BaseModel):
    url: str
    label: str
    source_type: SourceType = SourceType.other


class RawPage(BaseModel):
    url: str
    depth: int = 0
    status_code: int = 200
    content_type: str = "text/html"
    title: str | None = None
    text: str = ""
    raw_html: str | None = None
    links: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=utcnow)
    fingerprint: str = ""


class FactRecord(BaseModel):
    key: str
    value: Any
    source_url: str
    confidence: float = 1.0


class ProfileSection(BaseModel):
    section_type: SectionType
    title: str
    content: str
    source_url: str


class FacultyProfile(BaseModel):
    slug: str
    name: str
    english_name: str | None = None
    university: str
    school: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    homepage_url: str | None = None
    lab_url: str | None = None
    research_keywords: list[str] = Field(default_factory=list)
    facts: list[FactRecord] = Field(default_factory=list)
    sections: list[ProfileSection] = Field(default_factory=list)
    sources: list[SourceRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbeddingChunk(BaseModel):
    faculty_slug: str
    chunk_id: str
    content: str
    source_url: str
    section_type: SectionType
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchFilters(BaseModel):
    university: str | None = None
    school: str | None = None
    universities: list[str] = Field(default_factory=list)
    schools: list[str] = Field(default_factory=list)
    tiers: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    require_admissions: bool = False
    require_lab_url: bool = False

    def normalized_universities(self) -> list[str]:
        values = [*self.universities]
        if self.university:
            values.append(self.university)
        return list(dict.fromkeys(item for item in values if item))

    def normalized_schools(self) -> list[str]:
        values = [*self.schools]
        if self.school:
            values.append(self.school)
        return list(dict.fromkeys(item for item in values if item))

    def normalized_tiers(self) -> list[str]:
        return list(dict.fromkeys(item for item in self.tiers if item))


class SearchHit(BaseModel):
    faculty_slug: str
    faculty_name: str
    score: float
    section_type: SectionType
    snippet: str
    source_url: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    query: str
    filters: SearchFilters
    hits: list[SearchHit]


class AnswerResult(BaseModel):
    query: str
    filters: SearchFilters
    answer: str
    hits: list[SearchHit]
