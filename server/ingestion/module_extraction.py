from dataclasses import dataclass

from pydantic import BaseModel, Field

from ai.context import estimate_tokens
from ai.llm_client import LLMClient
from ai.structured import structured_completion
from engine.packs import (
    CrewTypeTemplate,
    ExtractedTable,
    FactionSeed,
    Item,
    PlaybookTemplate,
    SpecialAbility,
)

# Conservative budget leaving headroom for the system/schema instructions
# and the model's own structured output, inside the 64k floor ADR-0003
# sizes the GM's own turn context to - this is a one-shot extraction call,
# not a per-turn budget, but the same floor is the only number this
# project has settled on for "how much context can we assume".
EXTRACTION_TEXT_BUDGET_TOKENS = 40_000

_SYSTEM_PROMPT = (
    "You extract structured game content from a Forged in the Dark hack's "
    "rulebook text (FR-22). Only include entries clearly present in the "
    "text - never invent playbooks, items, abilities, factions, or tables "
    "that aren't there. Leave a category empty if the text doesn't cover "
    "it. This is a best-effort first pass; a human reviews and edits the "
    "result before any of it is used in a campaign."
)


class ModuleDraft(BaseModel):
    """FR-22: an LLM's best-effort structured extraction from a rulebook's
    normalised text (FR-21) - not yet a committed `ContentPack` (FR-9),
    though it reuses the same nested shapes (`engine/packs.py`) so
    finalising a reviewed draft (`ingestion/module_review.py`) is a
    straight assembly, not a translation. The user reviews and edits this
    before anything activates in a campaign (a separate step); it's never
    persisted or committed by this step itself (FR-23, C6 - private-module
    storage is its own job)."""

    playbooks: list[PlaybookTemplate] = Field(default_factory=list)
    crew_types: list[CrewTypeTemplate] = Field(default_factory=list)
    items: list[Item] = Field(default_factory=list)
    special_abilities: list[SpecialAbility] = Field(default_factory=list)
    factions: list[FactionSeed] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)


@dataclass
class ModuleExtractionResult:
    draft: ModuleDraft
    truncated: bool


def _fit_text(text: str, budget_tokens: int) -> tuple[str, bool]:
    """`estimate_tokens` is characters/4 (ai/context.py); inverted back to
    a character cutoff here since that's what slicing needs."""
    if estimate_tokens(text) <= budget_tokens:
        return text, False
    return text[: budget_tokens * 4], True


async def extract_module_draft(client: LLMClient, text: str) -> ModuleExtractionResult:
    """FR-22: the ingestion pipeline's second step - FR-21's normalised
    text, through an LLM structured completion (NFR-6), into the same
    content-pack shapes FR-9 already defines. `truncated` tells the
    caller (and eventually the review step) the draft may be incomplete
    just because the source text didn't fit the extraction budget, not
    only because of the model's own best-effort limits."""
    fitted_text, truncated = _fit_text(text, EXTRACTION_TEXT_BUDGET_TOKENS)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": fitted_text},
    ]
    draft = await structured_completion(client, messages, ModuleDraft)
    return ModuleExtractionResult(draft=draft, truncated=truncated)
