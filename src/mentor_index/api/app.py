from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from mentor_index.core.config import load_settings
from mentor_index.db.repository import Repository
from mentor_index.providers.embedding import build_embedding_provider
from mentor_index.providers.llm import build_llm_provider
from mentor_index.retrieve.service import RetrievalService

app = FastAPI(title="MentorDB API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_settings():
    return load_settings()


@lru_cache(maxsize=1)
def get_repository():
    settings = get_settings()
    return Repository(settings.database_url)


@lru_cache(maxsize=1)
def get_retrieval():
    settings = get_settings()
    repository = get_repository()
    embedding_provider = build_embedding_provider(settings)
    llm_provider = build_llm_provider(settings)
    return RetrievalService(repository, embedding_provider, llm_provider)


@app.get("/api/meta/filters")
def get_filters():
    return get_repository().load_filter_metadata()


@app.get("/api/search/faculty")
def search_faculty(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=50),
    university: str | None = None,
    school: str | None = None,
    require_admissions: bool = False,
    require_lab_url: bool = False,
):
    return get_retrieval().search_with_profiles(
        query=q,
        university=university,
        school=school,
        require_admissions=require_admissions,
        require_lab_url=require_lab_url,
        top_k=top_k,
    )


@app.get("/api/faculty/{slug}")
def get_faculty(slug: str):
    payload = get_repository().load_profile_detail(slug)
    if payload is None:
        raise HTTPException(status_code=404, detail="Faculty not found")
    return payload


@app.get("/api/faculty/{slug}/sources")
def get_faculty_sources(slug: str):
    payload = get_repository().load_profile_sources(slug)
    if payload is None:
        raise HTTPException(status_code=404, detail="Faculty not found")
    return payload
