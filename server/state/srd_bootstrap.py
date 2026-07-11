import logging
from pathlib import Path

import httpx2 as httpx
from sqlalchemy import text

from state.db import make_engine, make_session_factory
from state.srd_index import chunk_srd, index_srd_chunks

logger = logging.getLogger(__name__)

# bladesinthedark.com/downloads links this GitHub repo as the source of the
# SRD text (CC-BY 3.0, One Seven Design); pinned to main. Shared with
# cli/fetch_srd.py, which downloads the same file to the repo root for dev.
SRD_URL = (
    "https://raw.githubusercontent.com/amazingrando/"
    "blades-in-the-dark-srd-content/main/Blades-in-the-Dark-SRD.md"
)


async def ensure_srd_indexed(
    db_path: Path, transport: httpx.AsyncBaseTransport | None = None
) -> int | None:
    """FR-13: make sure app.db has an SRD retrieval corpus, fetching and
    indexing the SRD (CC-BY) from its official source if it has none.
    Exists for containerised deployments (SRD_AUTOINDEX=1 in the image):
    they have no local SRD copy and no dev CLI to run `make index-srd`,
    so without this the GM's retrieval would be silently empty. A no-op
    when chunks already exist, so it doesn't re-download on every boot;
    a failed download degrades to no retrieval (logged, not raised) and
    is retried on the next start, since the index is still empty.

    Returns the number of chunks indexed, or None if skipped or failed.
    Assumes migrations have already run (app startup order)."""
    engine = make_engine(db_path)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            existing = await session.execute(
                text("SELECT count(*) FROM srd_chunks WHERE source = 'srd'")
            )
            if existing.scalar_one() > 0:
                return None

        try:
            async with httpx.AsyncClient(follow_redirects=True, transport=transport) as client:
                response = await client.get(SRD_URL)
                response.raise_for_status()
        except httpx.HTTPError as error:
            logger.warning(
                "SRD auto-index: could not fetch the SRD (%s); the GM's rules "
                "retrieval stays empty until the next start succeeds",
                error,
            )
            return None

        chunks = chunk_srd(response.text)
        async with session_factory() as session:
            await index_srd_chunks(session, chunks)
        return len(chunks)
    finally:
        await engine.dispose()
