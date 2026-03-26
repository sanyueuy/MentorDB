from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class UniversityModel(Base):
    __tablename__ = "universities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    schools: Mapped[list["SchoolModel"]] = relationship(back_populates="university")


class SchoolModel(Base):
    __tablename__ = "schools"
    __table_args__ = (UniqueConstraint("university_id", "slug", name="uq_schools_university_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id"))
    slug: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    university: Mapped["UniversityModel"] = relationship(back_populates="schools")
    faculty_members: Mapped[list["FacultyModel"]] = relationship(back_populates="school")


class FacultyModel(Base):
    __tablename__ = "faculty"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    english_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    homepage_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lab_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    research_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    school: Mapped["SchoolModel"] = relationship(back_populates="faculty_members")
    sources: Mapped[list["SourceModel"]] = relationship(back_populates="faculty", cascade="all, delete-orphan")
    pages: Mapped[list["PageModel"]] = relationship(back_populates="faculty", cascade="all, delete-orphan")
    facts: Mapped[list["FactModel"]] = relationship(back_populates="faculty", cascade="all, delete-orphan")
    sections: Mapped[list["ProfileSectionModel"]] = relationship(back_populates="faculty", cascade="all, delete-orphan")
    embeddings: Mapped[list["EmbeddingModel"]] = relationship(back_populates="faculty", cascade="all, delete-orphan")


class SourceModel(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("faculty_id", "url", name="uq_sources_faculty_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id"))
    url: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(64))

    faculty: Mapped["FacultyModel"] = relationship(back_populates="sources")


class PageModel(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id"), index=True)
    url: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String(255))
    text_content: Mapped[str] = mapped_column(Text)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    status_code: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    faculty: Mapped["FacultyModel"] = relationship(back_populates="pages")
    documents: Mapped[list["DocumentModel"]] = relationship(back_populates="page", cascade="all, delete-orphan")
    links: Mapped[list["LinkModel"]] = relationship(back_populates="page", cascade="all, delete-orphan")


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"))
    doc_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    page: Mapped["PageModel"] = relationship(back_populates="documents")


class LinkModel(Base):
    __tablename__ = "links"
    __table_args__ = (UniqueConstraint("page_id", "url", name="uq_links_page_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"))
    url: Mapped[str] = mapped_column(Text)
    anchor_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)

    page: Mapped["PageModel"] = relationship(back_populates="links")


class FactModel(Base):
    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id"))
    fact_key: Mapped[str] = mapped_column(String(128))
    fact_value: Mapped[object] = mapped_column(JSON)
    source_url: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    faculty: Mapped["FacultyModel"] = relationship(back_populates="facts")


class ProfileSectionModel(Base):
    __tablename__ = "profile_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id"))
    section_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)

    faculty: Mapped["FacultyModel"] = relationship(back_populates="sections")


class EmbeddingModel(Base):
    __tablename__ = "embeddings"
    __table_args__ = (UniqueConstraint("faculty_id", "chunk_id", name="uq_embeddings_faculty_chunk"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id"))
    chunk_id: Mapped[str] = mapped_column(String(255))
    section_type: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    embedding_json: Mapped[list[float]] = mapped_column("embedding", JSON)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    faculty: Mapped["FacultyModel"] = relationship(back_populates="embeddings")


class CrawlRunModel(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    adapter_name: Mapped[str] = mapped_column(String(255))
    scope: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ChangeEventModel(Base):
    __tablename__ = "change_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id"))
    page_url: Mapped[str] = mapped_column(Text)
    change_type: Mapped[str] = mapped_column(String(64))
    old_fingerprint: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    new_fingerprint: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def build_engine(database_url: str):
    return create_engine(database_url, future=True)


def build_session_factory(database_url: str):
    return sessionmaker(bind=build_engine(database_url), expire_on_commit=False, future=True)
