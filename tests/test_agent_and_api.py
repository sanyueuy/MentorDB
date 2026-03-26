from __future__ import annotations

from fastapi.testclient import TestClient

from mentor_index.adapters.heuristic import HeuristicAdapterConfig, HeuristicDirectoryAdapter
from mentor_index.api.app import app
from mentor_index.collector.service import CollectorService
from mentor_index.core.models import RawPage
from mentor_index.core.utils import sha256_text
from mentor_index.db.repository import Repository
from mentor_index.extract.agent import ExtractAgent


class MemoryFetcher:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.settings = None

    def fetch(self, url: str, depth: int = 0):
        html = self.pages[url]
        return RawPage(
            url=url,
            depth=depth,
            status_code=200,
            content_type="text/html",
            title="page",
            text=html,
            raw_html=html,
            links=self.extract_links(html, url),
            fingerprint=sha256_text(html),
        )

    def extract_links(self, html: str, base_url: str):
        from mentor_index.crawl.agent import PageFetcher

        return PageFetcher._extract_html_metadata(html, base_url)[1]


def seed_generic_profile(repository: Repository, settings):
    adapter = HeuristicDirectoryAdapter(
        HeuristicAdapterConfig(
            university="测试大学",
            school="自动化学院",
            listing_url="https://example.edu/faculty",
        )
    )
    pages = {
        "https://example.edu/faculty": '<a href="https://example.edu/teacher/alice">Alice</a>',
        "https://example.edu/teacher/alice": """
        <html><body>
        <h1>Alice</h1>
        <h2>研究方向</h2><p>机器人 视觉</p>
        <a href="https://lab.example.com/alice">实验室</a>
        </body></html>
        """,
        "https://lab.example.com/alice": """
        <html><body>
        <h1>Robot Lab</h1>
        <h2>项目</h2><p>外链正文已抓取。</p>
        </body></html>
        """,
    }
    fetcher = MemoryFetcher(pages)
    listing = fetcher.fetch("https://example.edu/faculty")
    seed = adapter.list_faculty(listing)[0]
    crawled_pages = adapter.fetch_profile_pages(seed, settings.crawl_policy, fetcher)
    profile = ExtractAgent(adapter).build_profile(seed, crawled_pages)
    repository.upsert_profile(profile)
    repository.upsert_pages(profile.slug, crawled_pages)
    return profile


def test_heuristic_adapter_finds_faculty_and_external_page(repository, settings):
    profile = seed_generic_profile(repository, settings)
    detail = repository.load_profile_detail(profile.slug)

    assert detail is not None
    assert detail["name"] == "Alice"
    assert any(page["url"] == "https://lab.example.com/alice" for page in detail["external_pages"])


def test_collection_report_marks_external_sources(repository, settings):
    profile = seed_generic_profile(repository, settings)
    report = repository.build_collection_report(faculty_slug=profile.slug)

    assert report["faculty_count"] == 1
    assert report["faculties"][0]["external_crawled"] >= 1


def test_api_search_and_detail(repository, settings, monkeypatch):
    profile = seed_generic_profile(repository, settings)
    from mentor_index.api import app as api_module
    from mentor_index.providers.embedding import build_embedding_provider
    from mentor_index.providers.llm import build_llm_provider
    from mentor_index.index.embeddings import EmbeddingIndexer
    from mentor_index.retrieve.service import RetrievalService

    profiles = repository.load_profiles()
    EmbeddingIndexer(repository, build_embedding_provider(settings)).index_profiles(profiles)
    api_module.get_repository.cache_clear()
    api_module.get_retrieval.cache_clear()
    monkeypatch.setattr(api_module, "get_repository", lambda: repository)
    monkeypatch.setattr(
        api_module,
        "get_retrieval",
        lambda: RetrievalService(repository, build_embedding_provider(settings), build_llm_provider(settings)),
    )
    client = TestClient(app)

    search_response = client.get("/api/search/faculty", params={"q": "机器人"})
    detail_response = client.get(f"/api/faculty/{profile.slug}")

    assert search_response.status_code == 200
    assert search_response.json()["hits"]
    assert detail_response.status_code == 200
    assert detail_response.json()["external_pages"]
