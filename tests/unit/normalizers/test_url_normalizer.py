from farol_core.infrastructure.normalizers.url_normalizer import SimpleUrlNormalizer


def test_to_absolute_uses_base_url() -> None:
    normalizer = SimpleUrlNormalizer()

    result = normalizer.to_absolute("/path/article", "https://example.com/news/")

    assert result == "https://example.com/path/article"


def test_to_absolute_uses_default_base_url_when_not_provided() -> None:
    normalizer = SimpleUrlNormalizer(default_base_url="https://example.com/base/")

    result = normalizer.to_absolute("./relative")

    assert result == "https://example.com/relative"


def test_to_absolute_rejects_empty_input() -> None:
    normalizer = SimpleUrlNormalizer()

    try:
        normalizer.to_absolute(" ")
    except ValueError:
        pass
    else:  # pragma: no cover - segurança
        raise AssertionError("Era esperado ValueError para URL vazia")
