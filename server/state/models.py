from datetime import datetime

from sqlalchemy import UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class AppBase(DeclarativeBase):
    """Metadata for app.db (ADR-0005): capability cache, and later settings,
    SRD/FTS retrieval index, and installed content-pack state.

    Campaign files (campaign-<id>.db) have no models yet. Phase 1 built the
    event log itself as a pure engine construct (engine.events.EventLog,
    JSONL import/export) rather than a DB model, per "engine before
    interface"; SQLite-backed persistence of it is Phase 5 ("Campaign
    save/load from event log and snapshots"). Give campaign files their own
    base and Alembic lineage under state/ then, rather than sharing this one.
    """


class CapabilityProbe(AppBase):
    """Cached result of probing whether a given backend/model combination
    honours native tool-calling (NFR-6, ADR-0001); avoids re-probing on
    every session."""

    __tablename__ = "capability_probes"
    __table_args__ = (
        UniqueConstraint("base_url", "model", name="uq_capability_probes_base_url_model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    base_url: Mapped[str]
    model: Mapped[str]
    supports_tool_calling: Mapped[bool]
    probed_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
