from mentor_index.adapters.zju_control import ZjuControlAdapter
from mentor_index.core.utils import sha256_text
from mentor_index.db.models import ChangeEventModel
from mentor_index.extract.agent import ExtractAgent


def test_page_fingerprint_incremental_update(repository, fetcher, settings):
    adapter = ZjuControlAdapter()
    listing_page = fetcher.fetch(adapter.discover_seeds()[0].url)
    seed = adapter.list_faculty(listing_page)[0]
    pages = adapter.fetch_profile_pages(seed, settings.crawl_policy, fetcher)
    profile = ExtractAgent(adapter).build_profile(seed, pages)

    repository.upsert_profile(profile)
    assert repository.upsert_pages(profile.slug, pages) is True
    assert repository.upsert_pages(profile.slug, pages) is False

    updated_page = pages[0].model_copy(deep=True)
    updated_page.text += "\n新增了一条招生要求。"
    updated_page.fingerprint = sha256_text(updated_page.text)
    pages[0] = updated_page

    assert repository.upsert_pages(profile.slug, pages) is True
    with repository.session_factory() as session:
        events = session.query(ChangeEventModel).all()
        assert len(events) == 3
