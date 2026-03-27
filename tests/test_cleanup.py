from sqlalchemy import select

from mentor_index.db.models import PageModel, ProfileSectionModel, SourceModel


def test_cleanup_noise_removes_empty_pages_and_noisy_sections(repository, fetcher, settings):
    from mentor_index.adapters.zju_control import ZjuControlAdapter
    from mentor_index.extract.agent import ExtractAgent

    adapter = ZjuControlAdapter()
    listing_page = fetcher.fetch(adapter.discover_seeds()[0].url)
    seed = adapter.list_faculty(listing_page)[0]
    pages = adapter.fetch_profile_pages(seed, settings.crawl_policy, fetcher)
    profile = ExtractAgent(adapter).build_profile(seed, pages)
    faculty_id = repository.upsert_profile(profile)
    repository.upsert_pages(profile.slug, pages)

    with repository.session_factory.begin() as session:
        session.add(
            PageModel(
                faculty_id=faculty_id,
                url="https://person.zju.edu.cn/en/empty-profile",
                title=None,
                content_type="text/html",
                text_content="",
                depth=1,
                fingerprint="empty-page",
                status_code=200,
                metadata_json={},
                fetched_at=pages[0].fetched_at,
                is_active=True,
            )
        )
        session.add(
            SourceModel(
                faculty_id=faculty_id,
                url="https://person.zju.edu.cn/en/empty-profile",
                label="课题组/实验室",
                source_type="lab",
            )
        )
        session.add(
            ProfileSectionModel(
                faculty_id=faculty_id,
                section_type="other",
                title="Related People",
                content="Recommended by a third-party sidebar",
                source_url="https://person.zju.edu.cn/en/empty-profile",
            )
        )

    payload = repository.cleanup_noise()

    assert payload["deleted_pages"] >= 1
    assert payload["deleted_sources"] >= 1
    assert payload["deleted_sections"] >= 1

    with repository.session_factory() as session:
        assert session.scalar(select(PageModel).where(PageModel.url == "https://person.zju.edu.cn/en/empty-profile")) is None
        assert session.scalar(select(SourceModel).where(SourceModel.url == "https://person.zju.edu.cn/en/empty-profile")) is None
