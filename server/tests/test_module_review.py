from engine.pack_loader import FORBIDDEN_TERMS
from engine.packs import CrewTypeTemplate, ExtractedTable, FactionSeed, Item, PlaybookTemplate
from ingestion.module_extraction import ModuleDraft
from ingestion.module_review import finalize_module


def _draft() -> ModuleDraft:
    return ModuleDraft(
        playbooks=[PlaybookTemplate(id="prowler", name="Prowler", xp_trigger="...")],
        crew_types=[CrewTypeTemplate(id="raiders", name="Raiders")],
        items=[Item(id="grapple_gun", name="Grapple Gun")],
        factions=[FactionSeed(id="dock_wardens", name="The Dock Wardens", tier_hint=2)],
        tables=[
            ExtractedTable(
                name="Critical Injuries", columns=["Roll", "Injury"], rows=[["1", "Lost limb"]]
            )
        ],
    )


def test_finalize_module_assembles_a_content_pack_from_the_draft():
    pack = finalize_module(
        _draft(),
        pack_id="my-hack",
        name="My Hack",
        description="A homebrew FitD hack",
        version="0.1.0",
    )

    assert pack.id == "my-hack"
    assert pack.playbooks[0].name == "Prowler"
    assert pack.crew_types[0].name == "Raiders"
    assert pack.items[0].name == "Grapple Gun"
    assert pack.factions[0].name == "The Dock Wardens"
    assert pack.tables[0].name == "Critical Injuries"


def test_finalize_module_reflects_the_users_edits():
    # FR-22: "the user is the final validator" - editing the draft before
    # finalizing (standing in for a future web review UI) changes what
    # ends up in the resulting pack.
    draft = _draft()
    edited = draft.model_copy(
        update={
            "playbooks": [
                *draft.playbooks,
                PlaybookTemplate(id="whisper", name="Whisper", xp_trigger="..."),
            ]
        }
    )

    pack = finalize_module(
        edited, pack_id="my-hack", name="My Hack", description="desc", version="0.1.0"
    )

    assert {p.name for p in pack.playbooks} == {"Prowler", "Whisper"}


def test_finalize_module_allows_core_book_terms_in_a_private_module():
    # NOTICE.md/C6: owners may ingest core-book content they own into
    # private modules - the licensing firewall guards distribution
    # (licensing-grep, the committed packs/ loader), not user data.
    # Term drawn from FORBIDDEN_TERMS rather than hardcoded, so this test
    # file doesn't itself carry it as source text (licensing-grep) - same
    # reasoning as test_pack_loader.py's own test.
    forbidden_term = FORBIDDEN_TERMS[0]
    draft = ModuleDraft(items=[Item(id="lantern", name=f"A lantern from {forbidden_term}'s docks")])

    pack = finalize_module(draft, pack_id="my-book", name="n", description="d", version="0.1.0")

    assert forbidden_term in pack.items[0].name
