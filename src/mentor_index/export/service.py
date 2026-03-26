from __future__ import annotations

import json
from pathlib import Path

from mentor_index.core.models import FacultyProfile
from mentor_index.db.repository import Repository


class ExportService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def export_markdown_profiles(self, output_dir: str) -> int:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        profiles = self.repository.load_profiles()
        for profile in profiles:
            target = target_dir / f"{profile.slug}.md"
            target.write_text(self._profile_to_markdown(profile), encoding="utf-8")
        return len(profiles)

    def export_dataset(self, output_dir: str) -> int:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        profiles = self.repository.load_profiles()
        jsonl_path = target_dir / "faculty_profiles.jsonl"
        with jsonl_path.open("w", encoding="utf-8") as handle:
            for profile in profiles:
                handle.write(json.dumps(profile.model_dump(mode="json"), ensure_ascii=False) + "\n")
        return len(profiles)

    @staticmethod
    def _profile_to_markdown(profile: FacultyProfile) -> str:
        lines = [
            f"# {profile.name} - {profile.school}导师档案",
            "",
            "## 基础信息",
            f"- 学校：{profile.university}",
            f"- 学院：{profile.school}",
            f"- 职称：{profile.title or '未公开'}",
            f"- 邮箱：{profile.email or '未公开'}",
            f"- 电话：{profile.phone or '未公开'}",
            f"- 主页：{profile.homepage_url or '未公开'}",
            f"- 实验室：{profile.lab_url or '未公开'}",
            f"- 研究关键词：{', '.join(profile.research_keywords) or '未公开'}",
            "",
        ]
        for section in profile.sections:
            if section.title == "基础信息":
                continue
            lines.extend(
                [
                    f"## {section.title}",
                    section.content,
                    f"来源：{section.source_url}",
                    "",
                ]
            )
        lines.extend(["## 信息来源", ""])
        for source in profile.sources:
            lines.append(f"- {source.label}: {source.url}")
        lines.append("")
        return "\n".join(lines)
