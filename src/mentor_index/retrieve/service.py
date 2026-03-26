from __future__ import annotations

from mentor_index.core.models import AnswerResult, SearchFilters
from mentor_index.core.utils import cosine_similarity
from mentor_index.db.repository import Repository
from mentor_index.providers.embedding import EmbeddingProvider
from mentor_index.providers.llm import LLMProvider


class RetrievalService:
    def __init__(self, repository: Repository, embedding_provider: EmbeddingProvider, llm_provider: LLMProvider):
        self.repository = repository
        self.embedding_provider = embedding_provider
        self.llm_provider = llm_provider

    def search(self, query: str, filters: SearchFilters | None = None, top_k: int = 5):
        filters = filters or SearchFilters()
        rows = self.repository.load_index_rows(filters)
        if not rows:
            return self.repository.search_hits(query, filters, [], top_k)

        query_embedding = self.embedding_provider.embed([query])[0]
        scored: list[tuple[dict, float]] = []
        lowered_query = query.lower()
        for row in rows:
            cosine = cosine_similarity(query_embedding, row["embedding"])
            keyword_bonus = 0.08 if lowered_query[:8] and any(token in row["content"].lower() for token in lowered_query.split()) else 0.0
            rerank_bonus = self._rerank_bonus(lowered_query, row)
            scored.append((row, cosine + keyword_bonus + rerank_bonus))
        scored.sort(key=lambda item: item[1], reverse=True)
        return self.repository.search_hits(query, filters, scored, top_k)

    def answer(self, query: str, filters: SearchFilters | None = None, top_k: int = 5) -> AnswerResult:
        result = self.search(query=query, filters=filters, top_k=top_k)
        context = [
            f"[{hit.faculty_name}] {hit.section_type}: {hit.snippet}\nSource: {hit.source_url}"
            for hit in result.hits
        ]
        answer = self.llm_provider.answer(query=query, context_blocks=context)
        return AnswerResult(query=query, filters=result.filters, answer=answer, hits=result.hits)

    @staticmethod
    def _rerank_bonus(lowered_query: str, row: dict) -> float:
        section = row["section_type"]
        content = row["content"].lower()
        bonus = {
            "admissions": 0.06,
            "research": 0.04,
            "self_intro": 0.02,
            "mentoring": 0.01,
            "basic": -0.015,
        }.get(section, 0.0)

        admissions_terms = ("招生", "研究生", "硕士", "博士", "推免", "联系", "招")
        research_terms = ("方向", "研究", "机器人", "视觉", "ai", "人工智能", "系统", "控制")

        if any(term in lowered_query for term in admissions_terms):
            if section == "admissions":
                bonus += 0.14
            elif section == "research":
                bonus += 0.02
            elif section == "basic":
                bonus -= 0.03

        if any(term in lowered_query for term in research_terms):
            if section == "research":
                bonus += 0.1
            elif section == "basic":
                bonus -= 0.02

        if section == "admissions" and any(term in content for term in admissions_terms):
            bonus += 0.04
        if section == "research" and any(term in content for term in research_terms):
            bonus += 0.03

        return bonus
