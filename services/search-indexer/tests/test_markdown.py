from markdown import extract_plain_text


def test_strips_atx_headings():
    assert extract_plain_text("# Title\n\nBody.") == "Title Body."


def test_strips_bold_asterisk():
    assert extract_plain_text("This is **bold** text.") == "This is bold text."


def test_strips_italic_underscore():
    assert extract_plain_text("This is _italic_ text.") == "This is italic text."


def test_strips_inline_links():
    assert extract_plain_text("[Link text](https://example.com)") == "Link text"


def test_strips_images():
    assert extract_plain_text("![alt text](https://img.example.com/x.png)") == "alt text"


def test_strips_fenced_code_blocks():
    md = "Before\n```python\ncode = 1\n```\nAfter"
    result = extract_plain_text(md)
    assert "code = 1" not in result
    assert "Before" in result
    assert "After" in result


def test_strips_inline_code():
    result = extract_plain_text("Use the `x = 1` expression.")
    assert "`" not in result
    assert "x = 1" not in result


def test_normalizes_whitespace_to_single_spaces():
    result = extract_plain_text("Line one\n\nLine two")
    assert "\n" not in result
    assert "Line one" in result
    assert "Line two" in result


def test_empty_string_returns_empty():
    assert extract_plain_text("") == ""


def test_plain_text_passes_through():
    assert extract_plain_text("Just plain text.") == "Just plain text."
