from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
import uvicorn

from mentor_index.collector.service import CollectorService
from mentor_index.adapters.registry import get_adapter
from mentor_index.api.app import app as api_app
from mentor_index.core.config import AppSettings, load_settings
from mentor_index.core.models import FacultyProfile, FacultySeed, ProfileSection, SearchFilters, SectionType, SourceRecord, SourceType
from mentor_index.crawl.agent import PageFetcher
from mentor_index.db.repository import Repository
from mentor_index.export.service import ExportService
from mentor_index.extract.agent import ExtractAgent
from mentor_index.cli.formatting import format_answer_result, format_search_result, to_json
from mentor_index.index.embeddings import EmbeddingIndexer
from mentor_index.providers.embedding import build_embedding_provider
from mentor_index.providers.llm import build_llm_provider
from mentor_index.retrieve.service import RetrievalService

app = typer.Typer(help="Faculty crawling and retrieval system.")
crawl_app = typer.Typer(help="Crawl commands.")
search_app = typer.Typer(help="Search commands.")
index_app = typer.Typer(help="Index commands.")
build_app = typer.Typer(help="Build commands.")
export_app = typer.Typer(help="Export commands.")
agent_app = typer.Typer(help="Collector agent commands.")
app.add_typer(crawl_app, name="crawl")
app.add_typer(search_app, name="search")
app.add_typer(index_app, name="index")
app.add_typer(build_app, name="build")
app.add_typer(export_app, name="export")
app.add_typer(agent_app, name="agent")


def build_listing_only_profile(adapter, faculty_seed: FacultySeed) -> FacultyProfile:
    listing_entry = faculty_seed.metadata.get("listing_entry", {})
    title = listing_entry.get("work_title")
    listing_url = faculty_seed.metadata.get("listing_url", adapter.discover_seeds()[0].url)
    sections = [
        ProfileSection(
            section_type=SectionType.basic,
            title="基础信息",
            content="\n".join(
                [
                    f"姓名：{faculty_seed.name_hint or '未公开'}",
                    f"学院：{faculty_seed.school}",
                    f"职称：{title or '未公开'}",
                    f"主页：{faculty_seed.url}",
                    "状态：当前为名单级入库，详情待后续深度抓取。",
                ]
            ),
            source_url=listing_url,
        )
    ]
    sources = [
        SourceRecord(url=listing_url, label="学院检索页", source_type=SourceType.listing),
        SourceRecord(url=faculty_seed.url, label="教师个人主页", source_type=SourceType.homepage),
    ]
    return FacultyProfile(
        slug="",
        name=faculty_seed.name_hint or listing_entry.get("cn_name") or "未命名导师",
        university=faculty_seed.university,
        school=faculty_seed.school,
        title=title,
        homepage_url=faculty_seed.url,
        sections=sections,
        sources=sources,
        metadata={
            "listing_only": True,
            "mapping_name": listing_entry.get("mapping_name") or faculty_seed.url.rstrip("/").split("/")[-1],
            "listing_entry": listing_entry,
            "school_search_url": listing_url,
        },
    )


def bootstrap(settings: Optional[AppSettings] = None, *, with_models: bool = True):
    settings = settings or load_settings()
    repository = Repository(settings.database_url)
    repository.init_db()
    fetcher = PageFetcher(settings)
    embedding_provider = build_embedding_provider(settings) if with_models else None
    llm_provider = build_llm_provider(settings) if with_models else None
    retrieval = RetrievalService(repository, embedding_provider, llm_provider) if with_models else None
    exporter = ExportService(repository)
    return settings, repository, fetcher, embedding_provider, retrieval, exporter


def format_json_or_text(payload: dict, pretty: bool) -> str:
    if pretty:
        return "\n".join(f"{key}: {value}" for key, value in payload.items())
    return json.dumps(payload, ensure_ascii=False, indent=2)


@app.command("init-db")
def init_db():
    settings, repository, *_ = bootstrap(with_models=False)
    repository.init_db()
    typer.echo(f"Database initialized: {settings.database_url}")


@app.command("validate-adapter")
def validate_adapter(adapter_name: str):
    settings = load_settings()
    if settings.adapter_fixture_dir is None:
        settings.adapter_fixture_dir = str(Path.cwd() / "tests" / "fixtures")
    _, _, fetcher, *_ = bootstrap(settings, with_models=False)
    adapter = get_adapter(adapter_name)
    seeds = adapter.discover_seeds()
    if not seeds:
        raise typer.Exit(code=1)
    listing_page = adapter.fetch_listing_page(seeds[0], fetcher)
    faculty = adapter.list_faculty(listing_page)
    typer.echo(json.dumps({"adapter": adapter_name, "faculty_count": len(faculty)}, ensure_ascii=False))


@app.command("serve-api")
def serve_api(host: str = "127.0.0.1", port: int = 8000):
    uvicorn.run(api_app, host=host, port=port)


@crawl_app.command("school")
def crawl_school(
    adapter_name: str,
    seed_url: Optional[str] = None,
    limit: Optional[int] = None,
    listing_only: bool = False,
):
    settings, repository, fetcher, _, _, _ = bootstrap(with_models=False)
    adapter = get_adapter(adapter_name)
    run_id = repository.create_crawl_run(adapter_name, "school", {"seed_url": seed_url, "limit": limit})
    listing_seed = adapter.discover_seeds()[0]
    if seed_url:
        listing_seed = FacultySeed(
            university=listing_seed.university,
            school=listing_seed.school,
            url=seed_url,
            source_type=listing_seed.source_type,
        )
    listing_page = adapter.fetch_listing_page(listing_seed, fetcher)
    faculty_seeds = adapter.list_faculty(listing_page)
    if limit is not None:
        faculty_seeds = faculty_seeds[:limit]
    extract_agent = ExtractAgent(adapter)
    success_count = 0
    failed: list[dict[str, str | None]] = []
    for faculty_seed in faculty_seeds:
        try:
            if listing_only:
                profile = build_listing_only_profile(adapter, faculty_seed)
                profile = adapter.normalize_profile(profile.model_dump())
                repository.upsert_profile(profile)
            else:
                pages = adapter.fetch_profile_pages(faculty_seed, settings.crawl_policy, fetcher)
                profile = extract_agent.build_profile(faculty_seed, pages)
                repository.upsert_profile(profile)
                repository.upsert_pages(profile.slug, pages)
            success_count += 1
        except Exception as exc:
            failed.append(
                {
                    "name": faculty_seed.name_hint,
                    "url": faculty_seed.url,
                    "error": str(exc),
                }
            )
    repository.finish_crawl_run(run_id)
    typer.echo(
        json.dumps(
            {
                "adapter": adapter_name,
                "requested": len(faculty_seeds),
                "succeeded": success_count,
                "failed": len(failed),
                "listing_only": listing_only,
                "failures": failed[:20],
            },
            ensure_ascii=False,
        )
    )


@crawl_app.command("faculty")
def crawl_faculty(adapter_name: str, faculty_url: str, faculty_name: Optional[str] = None):
    settings, repository, fetcher, _, _, _ = bootstrap(with_models=False)
    adapter = get_adapter(adapter_name)
    run_id = repository.create_crawl_run(adapter_name, "faculty", {"faculty_url": faculty_url})
    seed = FacultySeed(
        university=adapter.university,
        school=adapter.school,
        name_hint=faculty_name,
        url=faculty_url,
        source_type=adapter.discover_seeds()[0].source_type,
    )
    pages = adapter.fetch_profile_pages(seed, settings.crawl_policy, fetcher)
    profile = ExtractAgent(adapter).build_profile(seed, pages)
    repository.upsert_profile(profile)
    repository.upsert_pages(profile.slug, pages)
    repository.finish_crawl_run(run_id)
    typer.echo(json.dumps({"adapter": adapter_name, "name": profile.name, "url": faculty_url}, ensure_ascii=False))


@index_app.command("embeddings")
def index_embeddings():
    settings, repository, _, embedding_provider, _, _ = bootstrap()
    profiles = repository.load_profiles()
    total = EmbeddingIndexer(repository, embedding_provider).index_profiles(profiles)
    typer.echo(f"Indexed {total} chunks")


@build_app.command("profiles")
def build_profiles(output_dir: str = "out/profiles"):
    _, repository, _, _, _, exporter = bootstrap(with_models=False)
    total = exporter.export_markdown_profiles(output_dir)
    typer.echo(f"Exported {total} markdown profiles to {output_dir}")


@export_app.command("dataset")
def export_dataset(output_dir: str = "out/dataset"):
    _, repository, _, _, _, exporter = bootstrap(with_models=False)
    total = exporter.export_dataset(output_dir)
    typer.echo(f"Exported {total} profiles to {output_dir}")


@search_app.command("faculty")
def search_faculty(
    query: str,
    top_k: int = 5,
    university: Optional[str] = None,
    school: Optional[str] = None,
    require_admissions: bool = False,
    require_lab_url: bool = False,
    pretty: bool = False,
    json_output: bool = typer.Option(False, "--json", help="Emit stable JSON output for agents and scripts."),
):
    _, _, _, _, retrieval, _ = bootstrap()
    filters = SearchFilters(
        university=university,
        school=school,
        require_admissions=require_admissions,
        require_lab_url=require_lab_url,
    )
    result = retrieval.search(query=query, filters=filters, top_k=top_k)
    typer.echo(format_search_result(result) if pretty else to_json(result) if json_output or not pretty else format_search_result(result))


@app.command("answer")
def answer(
    query: str,
    top_k: int = 5,
    university: Optional[str] = None,
    school: Optional[str] = None,
    pretty: bool = False,
    json_output: bool = typer.Option(False, "--json", help="Emit stable JSON output for agents and scripts."),
):
    _, _, _, _, retrieval, _ = bootstrap()
    filters = SearchFilters(university=university, school=school)
    result = retrieval.answer(query=query, filters=filters, top_k=top_k)
    typer.echo(format_answer_result(result) if pretty else to_json(result) if json_output or not pretty else format_answer_result(result))


@agent_app.command("discover")
def agent_discover(
    school: Optional[str] = None,
    university: Optional[str] = None,
    listing_url: Optional[str] = None,
    pretty: bool = False,
):
    settings, repository, *_ = bootstrap(with_models=False)
    collector = CollectorService(settings, repository)
    payload = {
        "candidates": [
            {
                "adapter_name": item.adapter_name,
                "university": item.university,
                "school": item.school,
                "listing_url": item.listing_url,
                "mode": item.mode,
                "confidence": item.confidence,
                "notes": item.notes,
                "preview_count": item.preview_count,
            }
            for item in collector.discover(school=school, university=university, listing_url=listing_url)
        ]
    }
    typer.echo(format_json_or_text(payload, pretty))


@agent_app.command("preview")
def agent_preview(
    adapter_name: Optional[str] = None,
    school: Optional[str] = None,
    university: Optional[str] = None,
    listing_url: Optional[str] = None,
    limit: int = 10,
    pretty: bool = False,
):
    settings, repository, *_ = bootstrap(with_models=False)
    collector = CollectorService(settings, repository)
    payload = collector.preview(adapter_name=adapter_name, university=university, school=school, listing_url=listing_url, limit=limit)
    typer.echo(format_json_or_text(payload, pretty))


@agent_app.command("crawl")
def agent_crawl(
    adapter_name: Optional[str] = None,
    school: Optional[str] = None,
    university: Optional[str] = None,
    listing_url: Optional[str] = None,
    limit: Optional[int] = None,
    pretty: bool = False,
):
    settings, repository, *_ = bootstrap(with_models=False)
    collector = CollectorService(settings, repository)
    payload = collector.crawl(adapter_name=adapter_name, university=university, school=school, listing_url=listing_url, limit=limit)
    typer.echo(format_json_or_text(payload, pretty))


@agent_app.command("crawl-external")
def agent_crawl_external(faculty_slug: Optional[str] = None, limit: int = 20, pretty: bool = False):
    settings, repository, *_ = bootstrap(with_models=False)
    collector = CollectorService(settings, repository)
    payload = collector.crawl_external(faculty_slug=faculty_slug, limit=limit)
    typer.echo(format_json_or_text(payload, pretty))


@agent_app.command("report")
def agent_report(faculty_slug: Optional[str] = None, pretty: bool = False):
    settings, repository, *_ = bootstrap(with_models=False)
    collector = CollectorService(settings, repository)
    payload = collector.report(faculty_slug=faculty_slug)
    typer.echo(format_json_or_text(payload, pretty))
