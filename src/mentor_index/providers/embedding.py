from __future__ import annotations

from mentor_index.core.config import AppSettings


class EmbeddingProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class StubEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int = 256):
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        if not text:
            return vector
        compact = "".join(text.split())
        for idx, char in enumerate(compact):
            vector[(ord(char) + idx) % self.dimension] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str, device: str = "auto"):
        import torch
        from sentence_transformers import SentenceTransformer

        if device == "auto":
            if torch.backends.mps.is_built() and torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        self.device = device
        self.model = SentenceTransformer(model_name, device=device)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()


def build_embedding_provider(settings: AppSettings) -> EmbeddingProvider:
    if settings.embedding_backend == "stub":
        return StubEmbeddingProvider(settings.embedding_dimension)
    if settings.embedding_backend == "sentence-transformers":
        return SentenceTransformerEmbeddingProvider(settings.embedding_model, settings.embedding_device)
    raise ValueError(f"Unsupported embedding backend: {settings.embedding_backend}")
