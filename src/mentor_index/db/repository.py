from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import delete, func, or_, select

from mentor_index.core.models import EmbeddingChunk, FacultyProfile, RawPage, SearchFilters, SearchHit, SearchResult
from mentor_index.core.utils import domain_of, slugify
from mentor_index.db.models import (
    Base,
    ChangeEventModel,
    CrawlRunModel,
    EmbeddingModel,
    FactModel,
    FacultyModel,
    LinkModel,
    PageModel,
    ProfileSectionModel,
    SchoolModel,
    SourceModel,
    UniversityModel,
    build_engine,
    build_session_factory,
)


class Repository:
    SECTION_PRIORITY = {
        "basic": 0,
        "admissions": 1,
        "research": 2,
        "self_intro": 3,
        "mentoring": 4,
        "achievements": 5,
        "contact": 6,
        "source_note": 7,
        "other": 8,
    }

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = build_engine(database_url)
        self.session_factory = build_session_factory(database_url)

    def init_db(self) -> None:
        Base.metadata.create_all(self.engine)

    NOISE_SECTION_TITLES = {
        "Related People",
        "Abstract",
        "Co-authors",
        "Last updated",
        "Cited by View all",
        "引用次数 查看全部",
        "合著作者",
        "Similar content being viewed by others",
        "Section snippets",
        "References",
        "Introduction",
        "Related Links",
        "Cited by",
        "Related works",
    }

    def create_crawl_run(self, adapter_name: str, scope: str, parameters: dict) -> int:
        with self.session_factory.begin() as session:
            run = CrawlRunModel(
                adapter_name=adapter_name,
                scope=scope,
                status="running",
                parameters=parameters,
                started_at=datetime.now(timezone.utc),
            )
            session.add(run)
            session.flush()
            return run.id

    def finish_crawl_run(self, run_id: int, status: str = "completed") -> None:
        with self.session_factory.begin() as session:
            run = session.get(CrawlRunModel, run_id)
            if run is None:
                return
            run.status = status
            run.finished_at = datetime.now(timezone.utc)

    def _get_or_create_school(self, session, university_name: str, school_name: str) -> SchoolModel:
        university_slug = slugify(university_name)
        school_slug = slugify(school_name)
        university = session.scalar(select(UniversityModel).where(UniversityModel.slug == university_slug))
        if university is None:
            university = UniversityModel(
                slug=university_slug,
                name=university_name,
                created_at=datetime.now(timezone.utc),
            )
            session.add(university)
            session.flush()
        school = session.scalar(
            select(SchoolModel).where(
                SchoolModel.university_id == university.id,
                SchoolModel.slug == school_slug,
            )
        )
        if school is None:
            school = SchoolModel(
                university_id=university.id,
                slug=school_slug,
                name=school_name,
                created_at=datetime.now(timezone.utc),
            )
            session.add(school)
            session.flush()
        return school

    def upsert_profile(self, profile: FacultyProfile) -> int:
        with self.session_factory.begin() as session:
            school = self._get_or_create_school(session, profile.university, profile.school)
            faculty = session.scalar(select(FacultyModel).where(FacultyModel.slug == profile.slug))
            now = datetime.now(timezone.utc)
            if faculty is None:
                faculty = FacultyModel(
                    school_id=school.id,
                    slug=profile.slug,
                    name=profile.name,
                    english_name=profile.english_name,
                    title=profile.title,
                    email=profile.email,
                    phone=profile.phone,
                    homepage_url=profile.homepage_url,
                    lab_url=profile.lab_url,
                    research_keywords=profile.research_keywords,
                    metadata_json=profile.metadata,
                    created_at=now,
                    updated_at=now,
                )
                session.add(faculty)
                session.flush()
            else:
                faculty.school_id = school.id
                faculty.name = profile.name
                faculty.english_name = profile.english_name
                faculty.title = profile.title
                faculty.email = profile.email
                faculty.phone = profile.phone
                faculty.homepage_url = profile.homepage_url
                faculty.lab_url = profile.lab_url
                faculty.research_keywords = profile.research_keywords
                faculty.metadata_json = profile.metadata
                faculty.updated_at = now

            session.execute(delete(SourceModel).where(SourceModel.faculty_id == faculty.id))
            session.execute(delete(FactModel).where(FactModel.faculty_id == faculty.id))
            session.execute(delete(ProfileSectionModel).where(ProfileSectionModel.faculty_id == faculty.id))

            for source in profile.sources:
                session.add(
                    SourceModel(
                        faculty_id=faculty.id,
                        url=source.url,
                        label=source.label,
                        source_type=source.source_type.value,
                    )
                )
            for fact in profile.facts:
                session.add(
                    FactModel(
                        faculty_id=faculty.id,
                        fact_key=fact.key,
                        fact_value=fact.value,
                        source_url=fact.source_url,
                        confidence=fact.confidence,
                    )
                )
            for section in profile.sections:
                session.add(
                    ProfileSectionModel(
                        faculty_id=faculty.id,
                        section_type=section.section_type.value,
                        title=section.title,
                        content=section.content,
                        source_url=section.source_url,
                    )
                )
            return faculty.id

    def upsert_pages(self, faculty_slug: str, pages: Iterable[RawPage]) -> bool:
        changed = False
        with self.session_factory.begin() as session:
            faculty = session.scalar(select(FacultyModel).where(FacultyModel.slug == faculty_slug))
            if faculty is None:
                raise ValueError(f"Faculty {faculty_slug} must exist before storing pages")

            for page in pages:
                unique_links = sorted({link for link in page.links if link})
                existing = session.scalar(select(PageModel).where(PageModel.url == page.url))
                if existing is None:
                    existing = PageModel(
                        faculty_id=faculty.id,
                        url=page.url,
                        title=page.title,
                        content_type=page.content_type,
                        text_content=page.text,
                        depth=page.depth,
                        fingerprint=page.fingerprint,
                        status_code=page.status_code,
                        metadata_json=page.metadata,
                        fetched_at=page.fetched_at,
                        is_active=True,
                    )
                    session.add(existing)
                    session.flush()
                    for link in unique_links:
                        session.add(
                            LinkModel(
                                page_id=existing.id,
                                url=link,
                                anchor_text=None,
                                is_external=True,
                            )
                        )
                    session.add(
                        ChangeEventModel(
                            faculty_id=faculty.id,
                            page_url=page.url,
                            change_type="created",
                            old_fingerprint=None,
                            new_fingerprint=page.fingerprint,
                            created_at=datetime.now(timezone.utc),
                        )
                    )
                    changed = True
                    continue

                if existing.fingerprint != page.fingerprint:
                    session.add(
                        ChangeEventModel(
                            faculty_id=faculty.id,
                            page_url=page.url,
                            change_type="updated",
                            old_fingerprint=existing.fingerprint,
                            new_fingerprint=page.fingerprint,
                            created_at=datetime.now(timezone.utc),
                        )
                    )
                    existing.title = page.title
                    existing.content_type = page.content_type
                    existing.text_content = page.text
                    existing.depth = page.depth
                    existing.fingerprint = page.fingerprint
                    existing.status_code = page.status_code
                    existing.metadata_json = page.metadata
                    existing.fetched_at = page.fetched_at
                    existing.is_active = True
                    session.execute(delete(LinkModel).where(LinkModel.page_id == existing.id))
                    for link in unique_links:
                        session.add(
                            LinkModel(
                                page_id=existing.id,
                                url=link,
                                anchor_text=None,
                                is_external=True,
                            )
                        )
                    changed = True
                else:
                    existing.fetched_at = page.fetched_at
                    existing.is_active = True

        return changed

    def replace_embeddings(self, chunks_with_vectors: list[tuple[EmbeddingChunk, list[float]]]) -> None:
        with self.session_factory.begin() as session:
            faculty_slugs = sorted({chunk.faculty_slug for chunk, _ in chunks_with_vectors})
            faculty_by_slug = {
                faculty.slug: faculty
                for faculty in session.scalars(select(FacultyModel).where(FacultyModel.slug.in_(faculty_slugs)))
            }
            for slug, faculty in faculty_by_slug.items():
                session.execute(delete(EmbeddingModel).where(EmbeddingModel.faculty_id == faculty.id))
            for chunk, vector in chunks_with_vectors:
                faculty = faculty_by_slug[chunk.faculty_slug]
                session.add(
                    EmbeddingModel(
                        faculty_id=faculty.id,
                        chunk_id=chunk.chunk_id,
                        section_type=chunk.section_type.value,
                        content=chunk.content,
                        source_url=chunk.source_url,
                        embedding_json=vector,
                        metadata_json=chunk.metadata,
                    )
                )

    def cleanup_noise(self) -> dict[str, int]:
        with self.session_factory.begin() as session:
            empty_or_loading = or_(
                PageModel.text_content.like("%正在加载中%"),
                func.trim(func.coalesce(PageModel.text_content, "")) == "",
            )
            bad_pages = session.scalars(select(PageModel).where(empty_or_loading)).all()
            bad_page_urls = {page.url for page in bad_pages}
            deleted_documents = sum(len(page.documents) for page in bad_pages)
            deleted_links = sum(len(page.links) for page in bad_pages)
            for page in bad_pages:
                session.delete(page)

            deleted_sources = 0
            if bad_page_urls:
                bad_sources = session.scalars(select(SourceModel).where(SourceModel.url.in_(bad_page_urls))).all()
                deleted_sources += len(bad_sources)
                for source in bad_sources:
                    session.delete(source)

            noisy_sections = session.scalars(
                select(ProfileSectionModel).where(
                    or_(
                        ProfileSectionModel.title.in_(sorted(self.NOISE_SECTION_TITLES)),
                        ProfileSectionModel.content.like("%正在加载中%"),
                        func.trim(func.coalesce(ProfileSectionModel.content, "")) == "",
                    )
                )
            ).all()
            deleted_sections = len(noisy_sections)
            for section in noisy_sections:
                session.delete(section)

            return {
                "deleted_pages": len(bad_pages),
                "deleted_links": deleted_links,
                "deleted_documents": deleted_documents,
                "deleted_sources": deleted_sources,
                "deleted_sections": deleted_sections,
            }

    def load_index_rows(self, filters: SearchFilters | None = None) -> list[dict]:
        with self.session_factory() as session:
            stmt = (
                select(FacultyModel, EmbeddingModel)
                .join(EmbeddingModel, EmbeddingModel.faculty_id == FacultyModel.id)
                .order_by(FacultyModel.name)
            )
            rows = []
            for faculty, embedding in session.execute(stmt):
                if filters:
                    if filters.university:
                        university = faculty.school.university.name
                        if university != filters.university:
                            continue
                    if filters.school and faculty.school.name != filters.school:
                        continue
                    if filters.require_admissions:
                        has_admissions = any(section.section_type == "admissions" for section in faculty.sections)
                        if not has_admissions:
                            continue
                    if filters.require_lab_url and not faculty.lab_url:
                        continue
                    if filters.keywords and not any(
                        keyword in " ".join(faculty.research_keywords + [faculty.name, faculty.title or ""])
                        for keyword in filters.keywords
                    ):
                        continue
                rows.append(
                    {
                        "faculty_slug": faculty.slug,
                        "faculty_name": faculty.name,
                        "school": faculty.school.name,
                        "university": faculty.school.university.name,
                        "section_type": embedding.section_type,
                        "content": embedding.content,
                        "embedding": embedding.embedding_json,
                        "source_url": embedding.source_url,
                        "metadata": embedding.metadata_json,
                    }
                )
            return rows

    def load_profiles(self) -> list[FacultyProfile]:
        with self.session_factory() as session:
            faculty_rows = session.scalars(select(FacultyModel).order_by(FacultyModel.name)).all()
            profiles = []
            for faculty in faculty_rows:
                profiles.append(
                    FacultyProfile(
                        slug=faculty.slug,
                        name=faculty.name,
                        english_name=faculty.english_name,
                        university=faculty.school.university.name,
                        school=faculty.school.name,
                        title=faculty.title,
                        email=faculty.email,
                        phone=faculty.phone,
                        homepage_url=faculty.homepage_url,
                        lab_url=faculty.lab_url,
                        research_keywords=faculty.research_keywords,
                        facts=[
                            {
                                "key": fact.fact_key,
                                "value": fact.fact_value,
                                "source_url": fact.source_url,
                                "confidence": fact.confidence,
                            }
                            for fact in sorted(faculty.facts, key=lambda item: item.fact_key)
                        ],
                        sections=[
                            {
                                "section_type": section.section_type,
                                "title": section.title,
                                "content": section.content,
                                "source_url": section.source_url,
                            }
                            for section in sorted(
                                faculty.sections,
                                key=lambda item: (self.SECTION_PRIORITY.get(item.section_type, 99), item.title),
                            )
                        ],
                        sources=[
                            {
                                "url": source.url,
                                "label": source.label,
                                "source_type": source.source_type,
                            }
                            for source in sorted(faculty.sources, key=lambda item: item.url)
                        ],
                        metadata=faculty.metadata_json,
                    )
                )
            return profiles

    def search_hits(self, query: str, filters: SearchFilters, scores: list[tuple[dict, float]], top_k: int) -> SearchResult:
        hits = [
            SearchHit(
                faculty_slug=row["faculty_slug"],
                faculty_name=row["faculty_name"],
                score=score,
                section_type=row["section_type"],
                snippet=row["content"][:280],
                source_url=row["source_url"],
                metadata=row["metadata"],
            )
            for row, score in scores[:top_k]
        ]
        return SearchResult(query=query, filters=filters, hits=hits)

    def load_faculty_cards(self, slugs: list[str]) -> dict[str, dict]:
        if not slugs:
            return {}
        with self.session_factory() as session:
            rows = session.scalars(select(FacultyModel).where(FacultyModel.slug.in_(slugs))).all()
            cards: dict[str, dict] = {}
            for faculty in rows:
                cards[faculty.slug] = {
                    "slug": faculty.slug,
                    "name": faculty.name,
                    "title": faculty.title,
                    "school": faculty.school.name,
                    "university": faculty.school.university.name,
                    "homepage_url": faculty.homepage_url,
                    "lab_url": faculty.lab_url,
                    "research_keywords": faculty.research_keywords,
                    "has_admissions": any(section.section_type == "admissions" for section in faculty.sections),
                    "source_count": len(faculty.sources),
                }
            return cards

    def load_profile_detail(self, slug: str) -> dict | None:
        with self.session_factory() as session:
            faculty = session.scalar(select(FacultyModel).where(FacultyModel.slug == slug))
            if faculty is None:
                return None
            pages_by_url = {page.url: page for page in faculty.pages}
            external_pages = []
            for page in sorted(faculty.pages, key=lambda item: item.url):
                if page.url == faculty.homepage_url:
                    continue
                if "person.zju.edu.cn" in page.url and page.url.startswith("https://person.zju.edu.cn"):
                    continue
                external_pages.append(
                    {
                        "url": page.url,
                        "title": page.title,
                        "content_type": page.content_type,
                        "summary": page.text_content[:400],
                        "metadata": page.metadata_json,
                    }
                )
            return {
                "slug": faculty.slug,
                "name": faculty.name,
                "title": faculty.title,
                "school": faculty.school.name,
                "university": faculty.school.university.name,
                "homepage_url": faculty.homepage_url,
                "lab_url": faculty.lab_url,
                "email": faculty.email,
                "phone": faculty.phone,
                "research_keywords": faculty.research_keywords,
                "metadata": faculty.metadata_json,
                "sections": [
                    {
                        "section_type": section.section_type,
                        "title": section.title,
                        "content": section.content,
                        "source_url": section.source_url,
                    }
                    for section in sorted(
                        faculty.sections,
                        key=lambda item: (self.SECTION_PRIORITY.get(item.section_type, 99), item.title),
                    )
                ],
                "sources": self._serialize_sources(faculty, pages_by_url),
                "external_pages": external_pages,
            }

    def load_profile_sources(self, slug: str) -> dict | None:
        with self.session_factory() as session:
            faculty = session.scalar(select(FacultyModel).where(FacultyModel.slug == slug))
            if faculty is None:
                return None
            pages_by_url = {page.url: page for page in faculty.pages}
            return {
                "slug": faculty.slug,
                "sources": self._serialize_sources(faculty, pages_by_url),
            }

    def load_filter_metadata(self) -> dict:
        with self.session_factory() as session:
            universities = session.scalars(select(UniversityModel).order_by(UniversityModel.name)).all()
            schools = session.scalars(select(SchoolModel).order_by(SchoolModel.name)).all()
            return {
                "universities": [item.name for item in universities],
                "schools": [item.name for item in schools],
            }

    def load_external_source_queue(self, faculty_slug: str | None = None, limit: int = 20) -> list[dict]:
        with self.session_factory() as session:
            stmt = select(FacultyModel, SourceModel).join(SourceModel, SourceModel.faculty_id == FacultyModel.id)
            rows = []
            for faculty, source in session.execute(stmt):
                if faculty_slug and faculty.slug != faculty_slug:
                    continue
                if source.source_type not in {"lab", "other", "project", "paper"}:
                    continue
                if source.url.startswith("fixture://"):
                    continue
                if source.url.startswith("https://person.zju.edu.cn"):
                    continue
                existing = session.scalar(select(PageModel).where(PageModel.url == source.url))
                if existing is not None:
                    continue
                source_origin = None
                diagnostics = (faculty.metadata_json or {}).get("external_link_diagnostics", {})
                for item in diagnostics.get("discovered", []):
                    if item.get("url") == source.url:
                        source_origin = item.get("origin")
                        break
                rows.append(
                    {
                        "faculty_slug": faculty.slug,
                        "url": source.url,
                        "source_type": source.source_type,
                        "origin": source_origin,
                    }
                )
                if len(rows) >= limit:
                    break
            return rows

    def build_collection_report(self, faculty_slug: str | None = None) -> dict:
        with self.session_factory() as session:
            stmt = select(FacultyModel).order_by(FacultyModel.name)
            faculties = []
            for faculty in session.scalars(stmt):
                if faculty_slug and faculty.slug != faculty_slug:
                    continue
                pages_by_url = {page.url for page in faculty.pages}
                source_rows = self._serialize_sources(faculty, {page.url: page for page in faculty.pages})
                external_discovered = sum(1 for source in source_rows if source["is_external"])
                external_crawled = sum(1 for source in source_rows if source["is_external"] and source["status"] == "crawled")
                discovery_summary = self._external_discovery_summary(faculty)
                faculties.append(
                    {
                        "slug": faculty.slug,
                        "name": faculty.name,
                        "school": faculty.school.name,
                        "external_discovered": external_discovered,
                        "external_crawled": external_crawled,
                        "external_discovery_sources": discovery_summary["sources"],
                        "external_statuses": discovery_summary["statuses"],
                        "missing_admissions": not any(section.section_type == "admissions" for section in faculty.sections),
                        "missing_homepage": faculty.homepage_url not in pages_by_url if faculty.homepage_url else True,
                    }
                )
            totals = {
                "sources": {},
                "statuses": {},
            }
            for faculty in faculties:
                for key, value in faculty["external_discovery_sources"].items():
                    totals["sources"][key] = totals["sources"].get(key, 0) + value
                for key, value in faculty["external_statuses"].items():
                    totals["statuses"][key] = totals["statuses"].get(key, 0) + value
            return {
                "faculty_count": len(faculties),
                "external_discovery_totals": totals,
                "faculties": faculties,
            }

    @staticmethod
    def _serialize_sources(faculty: FacultyModel, pages_by_url: dict[str, PageModel]) -> list[dict]:
        sources = []
        for source in sorted(faculty.sources, key=lambda item: item.url):
            page = pages_by_url.get(source.url)
            is_external = source.url != faculty.homepage_url and not source.url.startswith("https://person.zju.edu.cn")
            status = "crawled" if page is not None else "discovered"
            if source.source_type == "listing":
                status = "reference"
            final_url = page.metadata_json.get("final_url") if page is not None else None
            final_domain = domain_of(final_url) if final_url else None
            if is_external and page is not None and final_url and final_url.startswith("https://person.zju.edu.cn"):
                status = "redirected_internal"
            sources.append(
                {
                    "url": source.url,
                    "label": source.label,
                    "source_type": source.source_type,
                    "status": status,
                    "is_external": is_external,
                    "final_url": final_url,
                    "final_domain": final_domain,
                    "summary": page.text_content[:240] if page is not None else None,
                }
            )
        return sources

    @staticmethod
    def _external_discovery_summary(faculty: FacultyModel) -> dict[str, dict[str, int]]:
        diagnostics = (faculty.metadata_json or {}).get("external_link_diagnostics", {})
        source_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for item in diagnostics.get("discovered", []):
            origin = item.get("origin", "unknown")
            source_counts[origin] = source_counts.get(origin, 0) + 1
            status_counts["discovered"] = status_counts.get("discovered", 0) + 1
        for item in diagnostics.get("skipped", []):
            key = f"skipped:{item.get('reason', 'unknown')}"
            status_counts[key] = status_counts.get(key, 0) + 1
        for item in diagnostics.get("failed", []):
            status_counts["failed"] = status_counts.get("failed", 0) + 1
        for item in diagnostics.get("crawled", []):
            if item.get("redirected_back_internal") == "true":
                status_counts["redirected_internal"] = status_counts.get("redirected_internal", 0) + 1
            else:
                status_counts["crawled"] = status_counts.get("crawled", 0) + 1
        if not source_counts:
            for page in faculty.pages:
                discovery_sources = (page.metadata_json or {}).get("link_discovery_sources", {})
                for source_url in {source.url for source in faculty.sources}:
                    origins = discovery_sources.get(source_url, [])
                    for origin in origins:
                        source_counts[origin] = source_counts.get(origin, 0) + 1
        return {"sources": source_counts, "statuses": status_counts}
