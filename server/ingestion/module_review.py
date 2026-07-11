from engine.packs import ContentPack
from ingestion.module_extraction import ModuleDraft


def finalize_module(
    draft: ModuleDraft, *, pack_id: str, name: str, description: str, version: str
) -> ContentPack:
    """FR-22: the review/edit step's validation boundary. `draft` is
    whatever the user has reviewed and edited (a future web UI's job, not
    built yet - CLAUDE.md's "the engine may refuse; it never guesses"
    already applies for free here, since an edited draft that no longer
    matches `ModuleDraft`'s schema fails before this function ever runs).
    A module only "activates" - the FR-22 wording - once it assembles
    into a real `ContentPack` (FR-9): everything a draft carries maps
    straight across, since `ModuleDraft` reuses the same nested shapes.
    Not persisted or associated with any campaign here: FR-23's private
    storage is the next, separate step.

    Deliberately no licensing-firewall check: a private module is the
    user's own local data, and NOTICE.md explicitly allows owners to
    ingest core-book content they own (C6). The firewall guards
    distribution surfaces - commits (licensing-grep) and the committed
    `packs/` directory (`engine.pack_loader`) - not what stays on the
    user's machine."""
    return ContentPack(
        id=pack_id,
        name=name,
        description=description,
        version=version,
        playbooks=draft.playbooks,
        crew_types=draft.crew_types,
        items=draft.items,
        special_abilities=draft.special_abilities,
        factions=draft.factions,
        tables=draft.tables,
    )
