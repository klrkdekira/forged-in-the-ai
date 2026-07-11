import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_SRD_SOURCE = "srd"
_TOKEN_PATTERN = re.compile(r"\w+")


def _heading_level(line: str) -> int | None:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    return len(stripped) - len(stripped.lstrip("#"))


def _heading_text(line: str) -> str:
    return line.strip().lstrip("#").strip()


def module_source(pack_id: str) -> str:
    """FR-24: the `source` tag a module's own chunks are indexed and
    queried under - distinct per module so re-indexing one never touches
    another's rows, or the SRD's."""
    return f"module:{pack_id}"


@dataclass
class SrdChunkRecord:
    heading: str
    level: int
    line: int
    body: str
    source: str = _SRD_SOURCE


@dataclass
class SrdSearchHit:
    heading: str
    line: int
    body: str
    rank: float
    source: str = _SRD_SOURCE


def chunk_srd(srd_text: str) -> list[SrdChunkRecord]:
    """FR-13/ADR-0003: one chunk per SRD heading, body text up to the next
    heading of any level. Headings with no body text (e.g. immediately
    followed by another heading) are skipped."""
    lines = srd_text.splitlines()
    heading_positions = [i for i, line in enumerate(lines) if _heading_level(line) is not None]

    chunks = []
    for index, start in enumerate(heading_positions):
        end = heading_positions[index + 1] if index + 1 < len(heading_positions) else len(lines)
        body = "\n".join(lines[start + 1 : end]).strip()
        if not body:
            continue
        chunks.append(
            SrdChunkRecord(
                heading=_heading_text(lines[start]),
                level=_heading_level(lines[start]),
                line=start + 1,
                body=body,
            )
        )
    return chunks


def chunk_module_prose(
    pack_id: str, module_text: str, target_chunk_chars: int = 800
) -> list[SrdChunkRecord]:
    """FR-24: a module's own prose (setting material, GM advice), chunked
    for retrieval alongside the SRD. Unlike `chunk_srd`, this can't rely
    on markdown heading structure - an arbitrary uploaded book's
    normalised text (`ingestion/text_extraction.py`) has none once it's
    come out of a PDF - so paragraphs are grouped up to a size cap
    instead, with a synthetic heading (there's no real one to cite)."""
    paragraphs = [p.strip() for p in module_text.split("\n\n") if p.strip()]
    source = module_source(pack_id)
    chunks: list[SrdChunkRecord] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        if not current:
            return
        chunks.append(
            SrdChunkRecord(
                heading=f"{pack_id} (part {len(chunks) + 1})",
                level=0,
                line=len(chunks) + 1,
                body="\n\n".join(current),
                source=source,
            )
        )

    for paragraph in paragraphs:
        if current and current_len + len(paragraph) > target_chunk_chars:
            flush()
            current, current_len = [], 0
        current.append(paragraph)
        current_len += len(paragraph)
    flush()

    return chunks


def build_match_query(free_text: str) -> str:
    """Turns free text (e.g. a player's own message) into a safe FTS5
    MATCH expression: quoting each word token and OR-joining them
    sidesteps FTS5's own query syntax entirely, rather than trying to
    escape every special character (parentheses, hyphens, colons, etc.)
    free text might contain. "" for text with no word tokens at all -
    the caller should skip searching rather than MATCH on nothing."""
    tokens = _TOKEN_PATTERN.findall(free_text)
    return " OR ".join(f'"{token}"' for token in tokens)


async def _insert_chunks(session: AsyncSession, chunks: list[SrdChunkRecord]) -> None:
    for chunk in chunks:
        await session.execute(
            text(
                "INSERT INTO srd_chunks (heading, level, line, source, body) "
                "VALUES (:heading, :level, :line, :source, :body)"
            ),
            {
                "heading": chunk.heading,
                "level": chunk.level,
                "line": chunk.line,
                "source": chunk.source,
                "body": chunk.body,
            },
        )


async def index_srd_chunks(session: AsyncSession, chunks: list[SrdChunkRecord]) -> None:
    """Replaces the SRD's own chunks (source='srd') - never any module's,
    so re-running `make index-srd` doesn't silently drop every private
    module's retrieval content (FR-24)."""
    await session.execute(
        text("DELETE FROM srd_chunks WHERE source = :source"), {"source": _SRD_SOURCE}
    )
    await _insert_chunks(session, chunks)
    await session.commit()


async def index_module_chunks(
    session: AsyncSession, pack_id: str, chunks: list[SrdChunkRecord]
) -> None:
    """FR-24: replaces one module's own chunks only - re-saving/
    re-indexing a module never touches the SRD's chunks or any other
    module's."""
    source = module_source(pack_id)
    await session.execute(text("DELETE FROM srd_chunks WHERE source = :source"), {"source": source})
    await _insert_chunks(session, chunks)
    await session.commit()


async def search_srd(session: AsyncSession, query: str, limit: int = 5) -> list[SrdSearchHit]:
    """FR-13/FR-24: lexical (BM25) retrieval over the whole indexed corpus
    - SRD chunks and every indexed module's, ranked together in one query
    rather than as separately-scored result sets. `query` is passed as an
    FTS5 MATCH expression (`build_match_query` for free text)."""
    result = await session.execute(
        text(
            "SELECT heading, line, source, body, bm25(srd_chunks) AS rank FROM srd_chunks "
            "WHERE srd_chunks MATCH :query ORDER BY rank LIMIT :limit"
        ),
        {"query": query, "limit": limit},
    )
    return [SrdSearchHit(**row._mapping) for row in result]
