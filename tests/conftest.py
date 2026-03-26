from __future__ import annotations

from pathlib import Path

import pytest

from mentor_index.core.config import AppSettings
from mentor_index.crawl.agent import PageFetcher
from mentor_index.db.repository import Repository


@pytest.fixture()
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture()
def settings(tmp_path: Path, fixture_dir: Path) -> AppSettings:
    return AppSettings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'mentor_index.db'}",
        adapter_fixture_dir=str(fixture_dir),
        llm_base_url=None,
        llm_api_key=None,
        embedding_backend="stub",
    )


@pytest.fixture()
def repository(settings: AppSettings) -> Repository:
    repo = Repository(settings.database_url)
    repo.init_db()
    return repo


@pytest.fixture()
def fetcher(settings: AppSettings) -> PageFetcher:
    return PageFetcher(settings)
