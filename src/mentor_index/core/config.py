from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mentor_index.core.models import CrawlPolicy


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MENTOR_INDEX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite+pysqlite:///:memory:"
    embedding_backend: str = "sentence-transformers"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_dimension: int = 512
    embedding_device: str = "auto"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    user_agent: str = "mentor-index/0.1"
    max_crawl_depth: int = 2
    max_pages_per_faculty: int = 12
    max_external_domains: int = 8
    request_timeout_seconds: float = 15.0
    adapter_fixture_dir: str | None = None
    export_dataset_name: str = "mentor-index-dataset"
    browser_headless: bool = True
    browser_channel: str = "chrome"
    browser_timeout_ms: int = 45000
    browser_wait_after_load_ms: int = 3500
    browser_expand_max_clicks: int = 50
    zju_person_root: str = "https://person.zju.edu.cn"

    @property
    def crawl_policy(self) -> CrawlPolicy:
        return CrawlPolicy(
            max_depth=self.max_crawl_depth,
            max_pages_per_faculty=self.max_pages_per_faculty,
            max_external_domains=self.max_external_domains,
        )


def load_settings() -> AppSettings:
    return AppSettings()
