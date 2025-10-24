from datetime import datetime

from datetime import datetime

from farol_core.infrastructure.normalizers.date_normalizer import FlexibleDateNormalizer


def test_parse_handles_iso_strings() -> None:
    normalizer = FlexibleDateNormalizer()

    parsed = normalizer.parse("2024-01-10T10:30:00")

    assert parsed == datetime(2024, 1, 10, 10, 30, 0)


def test_parse_supports_relative_words_with_reference() -> None:
    reference = datetime(2024, 1, 10, 15, 0, 0)
    normalizer = FlexibleDateNormalizer()

    parsed = normalizer.parse("ontem", reference=reference)

    assert parsed == datetime(2024, 1, 9, 0, 0, 0)


def test_parse_returns_none_for_unknown_format() -> None:
    normalizer = FlexibleDateNormalizer(fallback_to_reference=False)

    assert normalizer.parse("data-invalida") is None
