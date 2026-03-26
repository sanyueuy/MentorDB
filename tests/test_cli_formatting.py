from mentor_index.cli.formatting import format_answer_result, format_search_result
from mentor_index.core.models import AnswerResult, SearchFilters, SearchHit, SearchResult, SectionType


def build_hit(section_type: SectionType = SectionType.admissions) -> SearchHit:
    return SearchHit(
        faculty_slug="zju-control-zhao",
        faculty_name="赵春晖",
        score=0.91,
        section_type=section_type,
        snippet="研究生招生信息：欢迎联系咨询。",
        source_url="https://person.zju.edu.cn/chhzhao#column-651795",
    )


def test_format_search_result_includes_human_readable_labels():
    result = SearchResult(query="找招研究生的老师", filters=SearchFilters(school="控制科学与工程学院"), hits=[build_hit()])

    rendered = format_search_result(result)

    assert "查询：找招研究生的老师" in rendered
    assert "学院=控制科学与工程学院" in rendered
    assert "赵春晖 | 招生说明" in rendered
    assert "来源：https://person.zju.edu.cn/chhzhao#column-651795" in rendered


def test_format_answer_result_lists_supporting_sources():
    result = AnswerResult(
        query="谁明确写了招生信息？",
        filters=SearchFilters(),
        answer="赵春晖明确写了研究生招生信息，并欢迎联系咨询。",
        hits=[build_hit(), build_hit(SectionType.research)],
    )

    rendered = format_answer_result(result)

    assert "回答：" in rendered
    assert "相关证据：" in rendered
    assert "赵春晖 | 招生说明" in rendered
