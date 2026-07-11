from ai.procedures import PROCEDURES, SESSION_ZERO_PROCEDURE

_ROLE_STATEMENT = (
    "You are the GM for a Forged in the Dark game. The rules engine rolls "
    "dice and tracks clocks, harm, stress, and heat; you narrate and make "
    "judgement calls, but every mechanical outcome comes from a tool call, "
    "never your own invention (FR-10, FR-12). If you're unsure of a rule, "
    "say so and defer to retrieval rather than guessing from memory (FR-13)."
)


def build_system_prompt(needs_session_zero: bool = False) -> str:
    """FR-11: the GM agent's always-present system prompt - role framing
    plus the distilled procedure docs (ADR-0003), kept within the 8k-token
    system-prompt budget (ADR-0003's context budget breakdown).

    `needs_session_zero` (FR-17/FR-36) adds the session-zero procedure
    only while a campaign hasn't set its canon/safety agreements yet -
    unlike PROCEDURES, it isn't always present, or every turn after
    session zero completes would re-run the interview."""
    sections = [_ROLE_STATEMENT]
    if needs_session_zero:
        sections.append(f"## {SESSION_ZERO_PROCEDURE.title}\n{SESSION_ZERO_PROCEDURE.text}")
    sections.extend(f"## {procedure.title}\n{procedure.text}" for procedure in PROCEDURES)
    return "\n\n".join(sections)
