from __future__ import annotations

from mentor_index.adapters.base import FacultyAdapter
from mentor_index.core.models import FacultyProfile, FacultySeed


class ExtractAgent:
    def __init__(self, adapter: FacultyAdapter):
        self.adapter = adapter

    def build_profile(self, faculty_seed: FacultySeed, pages) -> FacultyProfile:
        extracted = self.adapter.extract_entities(faculty_seed, pages)
        return self.adapter.normalize_profile(extracted)
