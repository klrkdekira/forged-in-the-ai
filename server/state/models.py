from datetime import datetime

from sqlalchemy import JSON, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class AppBase(DeclarativeBase):
    """Metadata for app.db (ADR-0005): capability cache, settings, SRD/FTS
    retrieval index, installed content-pack state, and the cross-campaign
    directory (CampaignIndex) - campaign gameplay state itself lives in its
    own file per campaign (CampaignBase, below)."""


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


class CampaignIndex(AppBase):
    """The list of campaigns (FR-18), so the web client can offer a
    "load campaign" picker without opening every campaign-<id>.db file.
    Each campaign's actual state lives only in its own file."""

    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class CampaignBase(DeclarativeBase):
    """Metadata for campaign-<id>.db files (ADR-0005): one file per
    campaign, holding that campaign's event log and latest state snapshot.
    Its own Alembic lineage (alembic_campaign/), separate from AppBase's,
    since these tables must not appear in app.db and vice versa."""


class EventRow(CampaignBase):
    """FR-19/FR-31: one entity-tagged event, mirroring engine.events.Event.
    Authoritative history; kept in sync with the embedded copy inside
    Snapshot.state_json so future replay/undo work (event log truncation)
    has a queryable table without a further migration."""

    __tablename__ = "events"

    sequence: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str]
    entity_id: Mapped[str]
    event_type: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    occurred_at: Mapped[datetime]


class Snapshot(CampaignBase):
    """FR-18/NFR-5: the cached, fast-path GameState for resuming a
    campaign - a single row (id is always 1, one snapshot per file), the
    full `GameState.model_dump_json()` including its embedded event log."""

    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    state_json: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
