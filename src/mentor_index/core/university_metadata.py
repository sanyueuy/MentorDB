from __future__ import annotations

from typing import TypedDict


class UniversityMetadata(TypedDict):
    name: str
    is_985: bool
    is_211: bool
    is_double_first_class: bool


UNIVERSITY_METADATA: dict[str, UniversityMetadata] = {
    "浙江大学": {
        "name": "浙江大学",
        "is_985": True,
        "is_211": True,
        "is_double_first_class": True,
    }
}


def tiers_for_university(name: str) -> list[str]:
    metadata = UNIVERSITY_METADATA.get(name)
    if not metadata:
        return []
    tiers: list[str] = []
    if metadata["is_985"]:
        tiers.append("985")
    if metadata["is_211"]:
        tiers.append("211")
    if metadata["is_double_first_class"]:
        tiers.append("double_first_class")
    return tiers


def metadata_for_university(name: str) -> UniversityMetadata | None:
    return UNIVERSITY_METADATA.get(name)
