from __future__ import annotations

from mentor_index.core.models import EmbeddingChunk, FacultyProfile


def build_chunks(profile: FacultyProfile, max_chars: int = 420) -> list[EmbeddingChunk]:
    chunks: list[EmbeddingChunk] = []
    for index, section in enumerate(profile.sections):
        paragraphs = [paragraph.strip() for paragraph in section.content.split("\n") if paragraph.strip()]
        buffer = ""
        part = 0
        for paragraph in paragraphs or [section.content]:
            candidate = f"{buffer}\n{paragraph}".strip() if buffer else paragraph
            if len(candidate) <= max_chars:
                buffer = candidate
                continue
            if buffer:
                chunks.append(
                    EmbeddingChunk(
                        faculty_slug=profile.slug,
                        chunk_id=f"{profile.slug}:{index}:{part}",
                        content=f"{section.title}\n{buffer}",
                        source_url=section.source_url,
                        section_type=section.section_type,
                    )
                )
                part += 1
            buffer = paragraph
        if buffer:
            chunks.append(
                EmbeddingChunk(
                    faculty_slug=profile.slug,
                    chunk_id=f"{profile.slug}:{index}:{part}",
                    content=f"{section.title}\n{buffer}",
                    source_url=section.source_url,
                    section_type=section.section_type,
                )
            )
    return chunks
