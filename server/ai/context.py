from dataclasses import dataclass, field

from state.srd_index import SrdSearchHit


def estimate_tokens(text: str) -> int:
    """A cheap, conservative token estimate (characters/4): no tokenizer
    dependency, good enough for budget enforcement, not exact accounting."""
    return (len(text) + 3) // 4 if text else 0


@dataclass
class ContextBudget:
    """ADR-0003's context budget breakdown (tokens), sized for the 64k
    floor (NFR-4). Total leaves headroom rather than summing to 64k."""

    system_and_procedures: int = 8_000
    canon: int = 10_000
    retrieval: int = 4_000
    transcript: int = 25_000


@dataclass
class CanonSection:
    """One piece of world-state canon (FR-15). Higher `priority` sections
    are kept first when the canon budget is tight."""

    title: str
    text: str
    priority: int = 0


@dataclass
class AssembledContext:
    system_prompt: str
    canon: str
    retrieval: str
    transcript: str
    dropped: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(
            section
            for section in (self.system_prompt, self.canon, self.retrieval, self.transcript)
            if section
        )

    def token_estimate(self) -> int:
        return estimate_tokens(self.full_text)


def _fit_canon(sections: list[CanonSection], budget: int) -> tuple[str, list[str]]:
    by_priority = sorted(sections, key=lambda s: s.priority, reverse=True)
    kept_titles: set[str] = set()
    dropped: list[str] = []
    used = 0
    for section in by_priority:
        cost = estimate_tokens(section.text)
        if used + cost <= budget:
            kept_titles.add(section.title)
            used += cost
        else:
            dropped.append(section.title)

    kept_in_order = [s for s in sections if s.title in kept_titles]
    return "\n\n".join(f"## {s.title}\n{s.text}" for s in kept_in_order), dropped


def _fit_retrieval(hits: list[SrdSearchHit], budget: int) -> tuple[str, list[str]]:
    kept: list[str] = []
    dropped: list[str] = []
    used = 0
    for hit in hits:  # already rank-ordered, best first
        text = f"### {hit.heading}\n{hit.body}"
        cost = estimate_tokens(text)
        if used + cost <= budget:
            kept.append(text)
            used += cost
        else:
            dropped.append(hit.heading)
    return "\n\n".join(kept), dropped


def _fit_transcript(lines: list[str], budget: int) -> tuple[str, int]:
    """Keeps the most recent lines (oldest-first input); older lines are
    summarised elsewhere (FR-15/FR-18) - this only enforces the cap."""
    kept: list[str] = []
    used = 0
    dropped = 0
    for line in reversed(lines):
        cost = estimate_tokens(line)
        if used + cost <= budget:
            kept.append(line)
            used += cost
        else:
            dropped += 1
    kept.reverse()
    return "\n".join(kept), dropped


def assemble_turn_context(
    system_prompt: str,
    canon_sections: list[CanonSection],
    retrieved: list[SrdSearchHit],
    transcript_lines: list[str],
    budget: ContextBudget | None = None,
) -> AssembledContext:
    """FR-15/NFR-4: assemble one GM turn's context - procedures, canon,
    retrieval, and a summarised transcript - under an explicit per-section
    budget, never by replaying the whole transcript."""
    budget = budget or ContextBudget()
    dropped: list[str] = []

    canon_text, dropped_canon = _fit_canon(canon_sections, budget.canon)
    dropped.extend(f"canon: {title}" for title in dropped_canon)

    retrieval_text, dropped_retrieval = _fit_retrieval(retrieved, budget.retrieval)
    dropped.extend(f"retrieval: {heading}" for heading in dropped_retrieval)

    transcript_text, dropped_transcript_count = _fit_transcript(transcript_lines, budget.transcript)
    if dropped_transcript_count:
        dropped.append(f"transcript: {dropped_transcript_count} older line(s) omitted")

    return AssembledContext(
        system_prompt=system_prompt,
        canon=canon_text,
        retrieval=retrieval_text,
        transcript=transcript_text,
        dropped=dropped,
    )
