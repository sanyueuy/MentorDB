from mentor_index.adapters.zju_control import ZjuControlAdapter
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
