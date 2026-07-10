from ai.context import (
    CanonSection,
    ContextBudget,
    assemble_turn_context,
    estimate_tokens,
)
from state.srd_index import SrdSearchHit


def test_estimate_tokens_is_roughly_chars_over_four():
    assert estimate_tokens("a" * 40) == 10
    assert estimate_tokens("") == 0


def test_assemble_turn_context_keeps_everything_under_budget():
    context = assemble_turn_context(
        system_prompt="You are the GM.",
        canon_sections=[CanonSection(title="Character", text="Test Character sheet.")],
        retrieved=[SrdSearchHit(heading="Armor", line=609, body="Mark an armor box.", rank=-1.0)],
        transcript_lines=["Player: I pick the lock.", "GM: Roll Finesse."],
    )

    assert "Character" in context.canon
    assert "Armor" in context.retrieval
    assert "pick the lock" in context.transcript
    assert not context.dropped


def test_assemble_turn_context_drops_lower_priority_canon_when_over_budget():
    # FR-15: higher-priority canon sections are kept first.
    budget = ContextBudget(system_and_procedures=100, canon=12, retrieval=100, transcript=100)
    sections = [
        CanonSection(title="Character", text="x" * 40, priority=2),
        CanonSection(title="Active clocks", text="y" * 40, priority=1),
    ]

    context = assemble_turn_context(
        system_prompt="", canon_sections=sections, retrieved=[], transcript_lines=[], budget=budget
    )

    assert "Character" in context.canon
    assert "Active clocks" not in context.canon
    assert "canon: Active clocks" in context.dropped


def test_assemble_turn_context_drops_lowest_ranked_retrieval_first():
    budget = ContextBudget(system_and_procedures=100, canon=100, retrieval=10, transcript=100)
    hits = [
        SrdSearchHit(heading="Best match", line=1, body="short", rank=-2.0),
        SrdSearchHit(heading="Worse match", line=2, body="z" * 100, rank=-1.0),
    ]

    context = assemble_turn_context(
        system_prompt="", canon_sections=[], retrieved=hits, transcript_lines=[], budget=budget
    )

    assert "Best match" in context.retrieval
    assert "Worse match" not in context.retrieval
    assert "retrieval: Worse match" in context.dropped


def test_assemble_turn_context_keeps_the_most_recent_transcript_lines():
    # NFR-4: "never by replaying whole transcripts" - oldest lines drop first.
    budget = ContextBudget(system_and_procedures=100, canon=100, retrieval=100, transcript=3)
    lines = ["oldest line here", "newest"]

    context = assemble_turn_context(
        system_prompt="", canon_sections=[], retrieved=[], transcript_lines=lines, budget=budget
    )

    assert context.transcript == "newest"
    assert any("transcript:" in note for note in context.dropped)


def test_token_estimate_reflects_the_assembled_sections():
    context = assemble_turn_context(
        system_prompt="short",
        canon_sections=[CanonSection(title="C", text="also short")],
        retrieved=[],
        transcript_lines=[],
    )

    assert context.token_estimate() == estimate_tokens(context.full_text)
