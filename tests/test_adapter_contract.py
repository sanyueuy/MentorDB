from mentor_index.adapters.zju_control import ZjuControlAdapter
from mentor_index.adapters.zju_person import SCHOOL_CONFIGS, ZjuPersonSearchAdapter
from mentor_index.extract.agent import ExtractAgent


def test_zju_adapter_lists_faculty(fetcher):
    adapter = ZjuControlAdapter()
    seed = adapter.discover_seeds()[0]
    listing_page = fetcher.fetch(seed.url)

    faculty = adapter.list_faculty(listing_page)

    assert len(faculty) == 2
    assert faculty[0].name_hint == "陈明"
    assert faculty[1].url.endswith("lixiao.html")


def test_zju_adapter_builds_profile_with_admissions_and_lab(fetcher, settings):
    adapter = ZjuControlAdapter()
    listing_page = fetcher.fetch(adapter.discover_seeds()[0].url)
    seed = adapter.list_faculty(listing_page)[0]

    pages = adapter.fetch_profile_pages(seed, settings.crawl_policy, fetcher)
    profile = ExtractAgent(adapter).build_profile(seed, pages)

    section_types = {section.section_type.value for section in profile.sections}
    assert profile.name == "陈明"
    assert profile.email == "chenming@zju.edu.cn"
    assert profile.lab_url.endswith("chenming_lab.html")
    assert "admissions" in section_types
    assert "mentoring" in section_types
    assert profile.metadata["has_admissions"] is True


def test_zju_extract_tab_titles_supports_static_onclick_tabs():
    adapter = ZjuPersonSearchAdapter(SCHOOL_CONFIGS["zju_control_real"])
    html = """
    <html><body>
      <ul class="person-nav">
        <li onclick="columnData(this,-1)" class="active">个人简介</li>
        <li onclick="columnData(this,983473)">教学与课程</li>
        <li onclick="columnData(this,983476)">研究与成果</li>
      </ul>
    </body></html>
    """

    titles = adapter._extract_tab_titles(html)

    assert titles["-1"] == "个人简介"
    assert titles["983473"] == "教学与课程"
    assert titles["983476"] == "研究与成果"
