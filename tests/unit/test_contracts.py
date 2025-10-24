from farol_core.domain.contracts import RawListingItem


def test_raw_listing_item_metadata_isolated() -> None:
    item = RawListingItem(url="https://example.com", content="html")
    item.metadata["key"] = "value"

    another = RawListingItem(url="https://example.org", content="html")

    assert "key" not in another.metadata
    assert another.metadata == {}
