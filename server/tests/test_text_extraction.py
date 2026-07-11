import pytest

from ingestion.text_extraction import UnsupportedFormatError, extract_text


def test_extract_text_from_plain_text():
    assert extract_text("notes.txt", b"Hello, world.") == "Hello, world."


def test_extract_text_from_markdown():
    assert extract_text("book.md", b"# Title\n\nSome body text.") == "# Title\n\nSome body text."


def test_extract_text_refuses_an_unsupported_extension():
    with pytest.raises(UnsupportedFormatError, match="unsupported file type"):
        extract_text("book.docx", b"whatever")


def test_extract_text_refuses_a_file_with_no_extension():
    with pytest.raises(UnsupportedFormatError):
        extract_text("book", b"whatever")


def test_extract_text_normalises_windows_line_endings():
    assert extract_text("notes.txt", b"line one\r\nline two\r\n") == "line one\nline two"


def test_extract_text_strips_trailing_whitespace_per_line():
    assert extract_text("notes.txt", b"line one   \nline two\t\n") == "line one\nline two"


def test_extract_text_collapses_runs_of_blank_lines():
    text = extract_text("notes.txt", b"one\n\n\n\n\ntwo")
    assert text == "one\n\ntwo"


def test_extract_text_strips_control_characters():
    text = extract_text("notes.txt", b"one\x00two\x07")
    assert text == "onetwo"


def test_extract_text_from_pdf(monkeypatch):
    # pypdf's own writer isn't a practical way to author text content in a
    # test fixture, so this stubs PdfReader itself rather than crafting a
    # real PDF binary - `_extract_pdf_text`'s only real job is joining
    # pages/handling a page with no extractable text, which this exercises
    # without depending on pypdf's actual parsing.
    class FakePage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class FakeReader:
        def __init__(self, _stream):
            self.pages = [FakePage("Page one."), FakePage(None), FakePage("Page three.")]

    monkeypatch.setattr("ingestion.text_extraction.PdfReader", FakeReader)

    text = extract_text("book.pdf", b"%PDF-1.4 fake bytes")

    # The blank middle page's "\n\n" separators collapse into the
    # normaliser's own "no more than one blank line in a row" rule.
    assert text == "Page one.\n\nPage three."
