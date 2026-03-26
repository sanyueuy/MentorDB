from pathlib import Path

from mentor_index.adapters.zju_control import ZjuControlAdapter
from mentor_index.export.service import ExportService
from mentor_index.extract.agent import ExtractAgent


def test_export_markdown_and_jsonl(repository, fetcher, settings, tmp_path: Path):
    adapter = ZjuControlAdapter()
    listing_page = fetcher.fetch(adapter.discover_seeds()[0].url)
    seed = adapter.list_faculty(listing_page)[0]
    profile = ExtractAgent(adapter).build_profile(seed, adapter.fetch_profile_pages(seed, settings.crawl_policy, fetcher))
    repository.upsert_profile(profile)

    exporter = ExportService(repository)
    markdown_dir = tmp_path / "profiles"
    dataset_dir = tmp_path / "dataset"

    exporter.export_markdown_profiles(str(markdown_dir))
    exporter.export_dataset(str(dataset_dir))

    markdown = next(markdown_dir.glob("*.md")).read_text(encoding="utf-8")
    jsonl = (dataset_dir / "faculty_profiles.jsonl").read_text(encoding="utf-8")

    assert "# 陈明" in markdown
    assert "招生说明" in markdown
    assert "陈明" in jsonl
