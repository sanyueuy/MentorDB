from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import delete, select

from mentor_index.core.models import EmbeddingChunk, FacultyProfile, RawPage, SearchFilters, SearchHit, SearchResult
from mentor_index.core.utils import slugify
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
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = build_engine(database_url)
        self.session_factory = build_session_factory(database_url)

    def init_db(self) -> None:
        Base.metadata.create_all(self.engine)

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
                            for section in sorted(faculty.sections, key=lambda item: (item.section_type, item.title))
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
