from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _heading_level(line: str) -> int | None:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    return len(stripped) - len(stripped.lstrip("#"))


def _heading_text(line: str) -> str:
    return line.strip().lstrip("#").strip()


@dataclass
class SrdChunkRecord:
    heading: str
    level: int
    line: int
    body: str


@dataclass
class SrdSearchHit:
    heading: str
    line: int
    body: str
    rank: float


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


async def index_srd_chunks(session: AsyncSession, chunks: list[SrdChunkRecord]) -> None:
    """Replaces the srd_chunks FTS5 table's contents (see the Alembic
    migration that creates it) with the given chunks."""
    await session.execute(text("DELETE FROM srd_chunks"))
    for chunk in chunks:
        await session.execute(
            text(
                "INSERT INTO srd_chunks (heading, level, line, body) "
                "VALUES (:heading, :level, :line, :body)"
            ),
            {
                "heading": chunk.heading,
                "level": chunk.level,
                "line": chunk.line,
                "body": chunk.body,
            },
        )
    await session.commit()


async def search_srd(session: AsyncSession, query: str, limit: int = 5) -> list[SrdSearchHit]:
    """FR-13: lexical (BM25) retrieval over indexed SRD chunks. `query`
    is passed as an FTS5 MATCH expression."""
    result = await session.execute(
        text(
            "SELECT heading, line, body, bm25(srd_chunks) AS rank FROM srd_chunks "
            "WHERE srd_chunks MATCH :query ORDER BY rank LIMIT :limit"
        ),
        {"query": query, "limit": limit},
    )
    return [SrdSearchHit(**row._mapping) for row in result]
