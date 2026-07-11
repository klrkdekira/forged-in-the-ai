import re
import unicodedata
from io import BytesIO

from pypdf import PdfReader

_SUPPORTED_SUFFIXES = (".pdf", ".md", ".markdown", ".txt")
_MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")


class UnsupportedFormatError(ValueError):
    """FR-21 covers PDF, markdown, and plain text only - any other upload
    is refused rather than guessed at (CLAUDE.md)."""


def extract_text(filename: str, content: bytes) -> str:
    """FR-21: the rulebook ingestion pipeline's first step (Phase 6) - a
    user's uploaded PDF/markdown/plain text file, reduced to normalised
    plain text. Turning that text into content-pack schemas is FR-22, a
    separate later step; this function's only job is getting clean text
    out of whatever was uploaded."""
    suffix = _suffix(filename)
    if suffix == ".pdf":
        raw = _extract_pdf_text(content)
    elif suffix in (".md", ".markdown", ".txt"):
        raw = content.decode("utf-8", errors="replace")
    else:
        raise UnsupportedFormatError(
            f"unsupported file type {suffix!r} - expected one of {_SUPPORTED_SUFFIXES}"
        )
    return _normalise(raw)


def _suffix(filename: str) -> str:
    _, _, extension = filename.rpartition(".")
    return f".{extension.lower()}" if extension else ""


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _normalise(text: str) -> str:
    """Consistent Unicode form and line endings, no control characters
    (PDF extraction in particular can leave stray ones behind), no
    trailing whitespace, and no more than one blank line in a row."""
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        ch for ch in text if ch in "\n\t" or not unicodedata.category(ch).startswith("C")
    )
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return _MULTIPLE_BLANK_LINES.sub("\n\n", text).strip()
