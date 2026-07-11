from pydantic import BaseModel, Field

from ai.llm_client import LLMClient
from ai.structured import structured_completion
from ai.tools import GameState, RollActionArgs, RollDecision
from engine.character import Character, StressTrack

_ROLE_STATEMENT = (
    "You are playing {name}, a crewmate PC in a Forged in the Dark game - not "
    "the GM, and not the human player at the table. Make choices {name} would "
    "make given their vice, their stress, and what's at stake right now; "
    "you're roleplaying a person, not optimising a dice pool (FR-35)."
)


def build_player_system_prompt(character: Character) -> str:
    """FR-35: the AI player agent's system prompt - distinct from the GM's
    (ai/system_prompt.py) and scoped to a single character's own voice and
    stakes, never the wider table's."""
    return _ROLE_STATEMENT.format(name=character.name)


class RoleplayLine(BaseModel):
    """Structured-completion schema (NFR-6) for `PlayerAgent.maybe_roleplay`.
    `speaks` defaults the model toward staying quiet: most GM narration
    doesn't call for a crewmate to chime in, and the alternative (a line
    every single turn) would drown out the human player."""

    speaks: bool = Field(
        False, description="Whether this character has something worth saying right now"
    )
    line: str | None = Field(None, description="What they say, in character, if speaks is true")


class PlayerAgent:
    """FR-35: an AI-controlled crewmate PC, distinct from the GM agent
    (ai/agent.py's GmAgent). Stands in for a human player for exactly the
    two things FR-35 names - deciding a proposed roll's bonus dice/trade-off
    (`decide_roll`, replacing the roll-negotiation dialog FR-16 otherwise
    pauses for) and occasional in-character roleplay (`maybe_roleplay`) -
    never anything that mutates state directly (CLAUDE.md rule 2): both
    return data the GM agent's own ToolExecutor calls apply."""

    def __init__(self, client: LLMClient, character_id: str) -> None:
        self._client = client
        self.character_id = character_id

    async def decide_roll(
        self, state: GameState, proposal: RollActionArgs, pool_size: int
    ) -> RollDecision:
        """FR-16/FR-35: the push/Devil's Bargain/trade-off decision a human
        would otherwise make in the roll-negotiation dialog, made instead
        by this character's own agent so the GM's tool-calling loop never
        has to pause for a human who isn't there."""
        character = state.characters[self.character_id]
        messages = [
            {"role": "system", "content": build_player_system_prompt(character)},
            {
                "role": "user",
                "content": (
                    f"The GM proposes a {proposal.action.value} roll at "
                    f"{proposal.position.value} position, {proposal.effect.name.lower()} "
                    f"effect. Your dice pool is {pool_size}. You have "
                    f"{character.stress.marked}/{StressTrack.MAX} stress marked already. "
                    "Decide whether to push yourself (more dice or more effect, at a stress "
                    "cost), accept a Devil's Bargain, trade position for effect or the "
                    "reverse, or just roll as proposed."
                ),
            },
        ]
        return await structured_completion(self._client, messages, RollDecision)

    async def maybe_roleplay(self, state: GameState, narration: str) -> str | None:
        """FR-35's "roleplay": an optional in-character line reacting to
        the GM's latest narration, logged the same way a human player's
        chat message is (ai/agent.py's GmAgent) so it joins the transcript
        for the GM's next turn - not answered live, since spotlight/turn
        management between controllers is FR-26, out of scope until
        multiplayer (Phase 7)."""
        character = state.characters[self.character_id]
        messages = [
            {"role": "system", "content": build_player_system_prompt(character)},
            {
                "role": "user",
                "content": (
                    f"The GM just narrated: {narration!r}\n"
                    "Only if it genuinely calls for it, add one short in-character line "
                    f"reacting as {character.name}. Most of the time you should stay quiet "
                    "and let the human player lead."
                ),
            },
        ]
        reply = await structured_completion(self._client, messages, RoleplayLine)
        return reply.line if reply.speaks and reply.line else None
