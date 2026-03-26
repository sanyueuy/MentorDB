from __future__ import annotations

import httpx

from mentor_index.core.config import AppSettings


class LLMProvider:
    def answer(self, query: str, context_blocks: list[str]) -> str:
        raise NotImplementedError


class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(self, settings: AppSettings):
        self.settings = settings

    def answer(self, query: str, context_blocks: list[str]) -> str:
        if not self.settings.llm_base_url or not self.settings.llm_api_key:
            return self._fallback_answer(query, context_blocks)

        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a retrieval assistant. Summarize results strictly from the provided evidence and mention source URLs inline.",
                },
                {
                    "role": "user",
                    "content": f"Query: {query}\n\nEvidence:\n" + "\n\n".join(context_blocks),
                },
            ],
            "temperature": 0.2,
        }
        with httpx.Client(
            timeout=self.settings.request_timeout_seconds,
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            response = client.post(f"{self.settings.llm_base_url.rstrip('/')}/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _fallback_answer(query: str, context_blocks: list[str]) -> str:
        preview = "\n".join(context_blocks[:3])
        return f"未配置云端 LLM，以下是与“{query}”最相关的证据摘要：\n{preview}"


def build_llm_provider(settings: AppSettings) -> LLMProvider:
    return OpenAICompatibleLLMProvider(settings)
