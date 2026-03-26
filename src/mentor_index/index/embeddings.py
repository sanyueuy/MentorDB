from __future__ import annotations

from mentor_index.core.models import FacultyProfile
from mentor_index.db.repository import Repository
from mentor_index.index.chunking import build_chunks
from mentor_index.providers.embedding import EmbeddingProvider


class EmbeddingIndexer:
    def __init__(self, repository: Repository, embedding_provider: EmbeddingProvider):
        self.repository = repository
        self.embedding_provider = embedding_provider

    def index_profiles(self, profiles: list[FacultyProfile]) -> int:
        chunks = []
        for profile in profiles:
            chunks.extend(build_chunks(profile))
        vectors = self.embedding_provider.embed([chunk.content for chunk in chunks]) if chunks else []
        self.repository.replace_embeddings(list(zip(chunks, vectors)))
        return len(chunks)
