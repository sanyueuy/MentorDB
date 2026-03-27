from __future__ import annotations

import json

from mentor_index.core.models import AnswerResult, SearchResult


SECTION_LABELS = {
    "basic": "基础信息",
    "self_intro": "导师自述",
    "research": "研究方向",
    "admissions": "招生说明",
    "mentoring": "培养与课程",
    "achievements": "成果项目",
    "links": "链接资料",
    "contact": "联系方式",
    "source_note": "来源提示",
    "other": "其他",
}


def format_search_result(result: SearchResult) -> str:
    lines = [f"查询：{result.query}"]
    selected_universities = result.filters.normalized_universities()
    selected_schools = result.filters.normalized_schools()
    selected_tiers = result.filters.normalized_tiers()
    if selected_universities or selected_schools or selected_tiers:
        filters = []
        if selected_universities:
            filters.append(f"学校={','.join(selected_universities)}")
        if selected_schools:
            filters.append(f"学院={','.join(selected_schools)}")
        if selected_tiers:
            filters.append(f"标签={','.join(selected_tiers)}")
        lines.append(f"筛选：{'，'.join(filters)}")
    if not result.hits:
        lines.append("未命中任何导师。")
        return "\n".join(lines)

    lines.append(f"命中 {len(result.hits)} 条证据：")
    for idx, hit in enumerate(result.hits, start=1):
        label = SECTION_LABELS.get(hit.section_type.value, hit.section_type.value)
        lines.extend(
            [
                f"{idx}. {hit.faculty_name} | {label} | 分数 {hit.score:.3f}",
                f"   摘要：{hit.snippet}",
                f"   来源：{hit.source_url}",
            ]
        )
    return "\n".join(lines)


def format_answer_result(result: AnswerResult) -> str:
    lines = [f"问题：{result.query}", "", "回答：", result.answer.strip()]
    if result.hits:
        lines.extend(["", "相关证据："])
        for idx, hit in enumerate(result.hits, start=1):
            label = SECTION_LABELS.get(hit.section_type.value, hit.section_type.value)
            lines.append(f"{idx}. {hit.faculty_name} | {label} | {hit.source_url}")
    return "\n".join(lines)


def to_json(payload: SearchResult | AnswerResult) -> str:
    return json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, indent=2)
