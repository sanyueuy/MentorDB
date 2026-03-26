from __future__ import annotations

from abc import ABC, abstractmethod

from mentor_index.core.models import CrawlPolicy, FacultyProfile, FacultySeed, RawPage


class FacultyAdapter(ABC):
    name: str
    university: str
    school: str

    def fetch_listing_page(self, listing_seed: FacultySeed, fetch_page) -> RawPage:
        return fetch_page.fetch(listing_seed.url)

    @abstractmethod
    def discover_seeds(self) -> list[FacultySeed]:
        raise NotImplementedError

    @abstractmethod
    def list_faculty(self, listing_page: RawPage) -> list[FacultySeed]:
        raise NotImplementedError

    @abstractmethod
    def fetch_profile_pages(
        self,
        faculty_seed: FacultySeed,
        crawl_policy: CrawlPolicy,
        fetch_page,
    ) -> list[RawPage]:
        raise NotImplementedError

    @abstractmethod
    def extract_entities(self, faculty_seed: FacultySeed, pages: list[RawPage]) -> dict:
        raise NotImplementedError

    @abstractmethod
    def normalize_profile(self, extracted: dict) -> FacultyProfile:
        raise NotImplementedError
