from mentor_index.extract.normalizer import extract_contacts


def test_extract_contacts_ignores_unlabeled_long_numeric_ids():
    facts = extract_contacts(
        "专利号: ZL 202510796282.9, 授权公告号: CN 120317258B",
        "https://example.com",
    )

    assert not any(fact.key == "phone" for fact in facts)


def test_extract_contacts_extracts_labeled_phone_and_email():
    facts = extract_contacts(
        "邮箱：chenming@zju.edu.cn 联系电话：0571-87951111",
        "https://example.com",
    )

    assert any(fact.key == "email" and fact.value == "chenming@zju.edu.cn" for fact in facts)
    assert any(fact.key == "phone" and fact.value == "0571-87951111" for fact in facts)
