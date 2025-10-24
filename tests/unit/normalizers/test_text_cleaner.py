from farol_core.infrastructure.normalizers.text_cleaner import SoupTextCleaner


def test_clean_html_to_text_removes_tags_and_whitespace() -> None:
    cleaner = SoupTextCleaner()

    raw_html = "<div>Olá <strong>mundo</strong>!<script>alert('x')</script></div>"

    assert cleaner.clean_html_to_text(raw_html) == "Olá mundo!"


def test_sanitize_html_preserves_allowed_tags_and_strips_others() -> None:
    cleaner = SoupTextCleaner(allowed_tags=("p", "a"))

    html = "<div><p onclick=\"bad()\">Olá <span>mundo</span> <a href=\"javascript:alert(1)\">link</a></p></div>"

    sanitized = cleaner.sanitize_html(html)

    assert "<span>" not in sanitized
    assert "onclick" not in sanitized
    assert "javascript" not in sanitized
    assert sanitized.startswith("<p>")
