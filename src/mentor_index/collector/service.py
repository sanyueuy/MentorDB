from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from mentor_index.adapters.heuristic import HeuristicAdapterConfig, HeuristicDirectoryAdapter
from mentor_index.adapters.registry import get_adapter
from mentor_index.adapters.zju_person import SCHOOL_CONFIGS
from mentor_index.core.config import AppSettings
from mentor_index.core.models import CrawlPolicy, FacultyProfile, FacultySeed, RawPage, SourceType
from mentor_index.crawl.agent import PageFetcher
from mentor_index.db.repository import Repository
from mentor_index.extract.agent import ExtractAgent


@dataclass
class DiscoveryCandidate:
    adapter_name: str
    university: str
    school: str
    listing_url: str
    mode: str
    confidence: str
    notes: list[str]
    preview_count: int = 0


class CollectorService:
    def __init__(self, settings: AppSettings, repository: Repository):
        self.settings = settings
        self.repository = repository
        self.fetcher = PageFetcher(settings)

    def discover(
        self,
        *,
        school: str | None = None,
        university: str | None = None,
        listing_url: str | None = None,
    ) -> list[DiscoveryCandidate]:
        candidates: list[DiscoveryCandidate] = []
        school = school or ""
        university = university or ""
        for adapter_name, config in SCHOOL_CONFIGS.items():
            if school and school not in config.school_name:
                continue
            if university and university not in "浙江大学":
                continue
            preview_count = self._preview_known_adapter(adapter_name)
            candidates.append(
                DiscoveryCandidate(
                    adapter_name=adapter_name,
                    university="浙江大学",
                    school=config.school_name,
                    listing_url=config.listing_url,
                    mode="known_adapter",
                    confidence="high",
                    notes=["项目内已有专用适配器。"],
                    preview_count=preview_count,
                )
            )
        if listing_url:
            parsed = urlparse(listing_url)
            inferred_school = school or parsed.netloc or "未命名学院"
            inferred_university = university or parsed.netloc or "未命名学校"
            preview_count = self._preview_heuristic(inferred_university, inferred_school, listing_url)
            notes = ["使用通用启发式发现导师主页。"]
            if preview_count == 0:
                notes.append("列表页未识别出明显导师链接，可能需要人工指定或新增适配器。")
            candidates.append(
                DiscoveryCandidate(
                    adapter_name="heuristic_directory",
                    university=inferred_university,
                    school=inferred_school,
                    listing_url=listing_url,
                    mode="heuristic",
                    confidence="medium" if preview_count else "low",
                    notes=notes,
                    preview_count=preview_count,
                )
            )
        return candidates

    def preview(
        self,
        *,
        adapter_name: str | None = None,
        university: str | None = None,
        school: str | None = None,
        listing_url: str | None = None,
        limit: int = 10,
    ) -> dict:
        adapter = self._resolve_adapter(adapter_name, university, school, listing_url)
        seed = adapter.discover_seeds()[0]
        listing_page = adapter.fetch_listing_page(seed, self.fetcher)
        faculty = adapter.list_faculty(listing_page)
        return {
            "adapter": adapter.name,
            "university": adapter.university,
            "school": adapter.school,
            "listing_url": seed.url,
            "count": len(faculty),
            "preview": [
                {
                    "name": item.name_hint,
                    "url": item.url,
                }
                for item in faculty[:limit]
            ],
        }

    def crawl(
        self,
        *,
        adapter_name: str | None = None,
        university: str | None = None,
        school: str | None = None,
        listing_url: str | None = None,
        limit: int | None = None,
    ) -> dict:
        adapter = self._resolve_adapter(adapter_name, university, school, listing_url)
        seed = adapter.discover_seeds()[0]
        listing_page = adapter.fetch_listing_page(seed, self.fetcher)
        faculty = adapter.list_faculty(listing_page)
        if limit is not None:
            faculty = faculty[:limit]

        success = 0
        failures: list[dict[str, str | None]] = []
        profiles: list[FacultyProfile] = []
        extract_agent = ExtractAgent(adapter)
        for item in faculty:
            try:
                pages = adapter.fetch_profile_pages(item, self.settings.crawl_policy, self.fetcher)
                profile = extract_agent.build_profile(item, pages)
                self.repository.upsert_profile(profile)
                self.repository.upsert_pages(profile.slug, pages)
                profiles.append(profile)
                success += 1
            except Exception as exc:
                failures.append({"name": item.name_hint, "url": item.url, "error": str(exc)})
        return {
            "adapter": adapter.name,
            "university": adapter.university,
            "school": adapter.school,
            "requested": len(faculty),
            "succeeded": success,
            "failed": len(failures),
            "failures": failures[:20],
            "profiles": [profile.slug for profile in profiles[:20]],
        }

    def crawl_external(self, faculty_slug: str | None = None, limit: int = 20) -> dict:
        rows = self.repository.load_external_source_queue(faculty_slug=faculty_slug, limit=limit)
        crawled = 0
        failures: list[dict[str, str]] = []
        for row in rows:
            try:
                page = self.fetcher.fetch(row["url"], depth=2)
                self.repository.upsert_pages(row["faculty_slug"], [page])
                crawled += 1
            except Exception as exc:
                failures.append({"faculty_slug": row["faculty_slug"], "url": row["url"], "error": str(exc)})
        return {
            "requested": len(rows),
            "crawled": crawled,
            "failed": len(failures),
            "failures": failures[:20],
        }

    def report(self, faculty_slug: str | None = None) -> dict:
        return self.repository.build_collection_report(faculty_slug=faculty_slug)

    def _resolve_adapter(
        self,
        adapter_name: str | None,
        university: str | None,
        school: str | None,
        listing_url: str | None,
    ):
        if adapter_name:
            return get_adapter(adapter_name)
        if listing_url:
            return HeuristicDirectoryAdapter(
                HeuristicAdapterConfig(
                    university=university or urlparse(listing_url).netloc or "未命名学校",
                    school=school or urlparse(listing_url).netloc or "未命名学院",
                    listing_url=listing_url,
                )
            )
        if school:
            for adapter_key, config in SCHOOL_CONFIGS.items():
                if school in config.school_name:
                    return get_adapter(adapter_key)
        raise ValueError("Missing adapter_name or listing_url for collector workflow")

    def _preview_known_adapter(self, adapter_name: str) -> int:
        adapter = get_adapter(adapter_name)
        seed = adapter.discover_seeds()[0]
        listing_page = adapter.fetch_listing_page(seed, self.fetcher)
        return len(adapter.list_faculty(listing_page))

    def _preview_heuristic(self, university: str, school: str, listing_url: str) -> int:
        adapter = HeuristicDirectoryAdapter(
            HeuristicAdapterConfig(university=university, school=school, listing_url=listing_url)
        )
        seed = adapter.discover_seeds()[0]
        listing_page = adapter.fetch_listing_page(seed, self.fetcher)
        return len(adapter.list_faculty(listing_page))
