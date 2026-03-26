from mentor_index.adapters.zju_control import ZjuControlAdapter
from mentor_index.extract.agent import ExtractAgent
from mentor_index.index.embeddings import EmbeddingIndexer
from mentor_index.providers.embedding import build_embedding_provider
from mentor_index.providers.llm import build_llm_provider
from mentor_index.retrieve.service import RetrievalService


def seed_profiles(repository, fetcher, settings):
    adapter = ZjuControlAdapter()
    listing_page = fetcher.fetch(adapter.discover_seeds()[0].url)
    seeds = adapter.list_faculty(listing_page)
    agent = ExtractAgent(adapter)
    profiles = []
    for seed in seeds:
        pages = adapter.fetch_profile_pages(seed, settings.crawl_policy, fetcher)
        profile = agent.build_profile(seed, pages)
        repository.upsert_profile(profile)
        repository.upsert_pages(profile.slug, pages)
        profiles.append(profile)
    return profiles


def test_search_returns_relevant_teacher(repository, fetcher, settings):
    profiles = seed_profiles(repository, fetcher, settings)
    EmbeddingIndexer(repository, build_embedding_provider(settings)).index_profiles(profiles)
    retrieval = RetrievalService(repository, build_embedding_provider(settings), build_llm_provider(settings))

    result = retrieval.search("自动化背景 代码能力 工程落地", top_k=3)

    assert result.hits
    assert result.hits[0].faculty_name == "陈明"


def test_answer_uses_fallback_without_cloud_llm(repository, fetcher, settings):
    profiles = seed_profiles(repository, fetcher, settings)
    EmbeddingIndexer(repository, build_embedding_provider(settings)).index_profiles(profiles)
    retrieval = RetrievalService(repository, build_embedding_provider(settings), build_llm_provider(settings))

    answer = retrieval.answer("哪些老师明确写了欢迎自动化背景并强调代码能力？", top_k=2)

    assert "未配置云端 LLM" in answer.answer
    assert "陈明" in answer.answer


def test_rerank_prefers_admissions_for_admissions_query(repository, fetcher, settings):
    profiles = seed_profiles(repository, fetcher, settings)
    EmbeddingIndexer(repository, build_embedding_provider(settings)).index_profiles(profiles)
    retrieval = RetrievalService(repository, build_embedding_provider(settings), build_llm_provider(settings))

    result = retrieval.search("我想找明确写了研究生招生信息的老师", top_k=5)

    assert result.hits
    assert result.hits[0].section_type.value == "admissions"
