from __future__ import annotations

import hashlib
import math
import re
from urllib.parse import urljoin, urlparse


def slugify(value: str) -> str:
    normalized = re.sub(r"\s+", "-", value.strip().lower())
    normalized = re.sub(r"[^0-9a-zA-Z\-\u4e00-\u9fff]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "unknown"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    numerator = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return numerator / (norm_a * norm_b)


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower()


def resolve_url(base_url: str, href: str) -> str:
    if base_url.startswith("fixture://") and not href.startswith(("fixture://", "http://", "https://", "/")):
        base_parts = base_url.split("/")
        base_dir = "/".join(base_parts[:-1])
        return f"{base_dir}/{href}"
    return urljoin(base_url, href)
