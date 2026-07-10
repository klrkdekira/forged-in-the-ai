from enum import StrEnum

from pydantic import BaseModel

from engine.errors import EngineError


class CampaignPhase(StrEnum):
    """SRD: "The Game Structure" - "By default, the game is in free play...
    the game shifts into the score phase... When the score is finished,
    the game shifts into the downtime phase... the game returns to free
    play and the cycle starts over again."""

    FREE_PLAY = "free_play"
    SCORE = "score"
    DOWNTIME = "downtime"


# SRD: "The Game Structure" - the one-way cycle described above.
_ALLOWED_TRANSITIONS: dict[CampaignPhase, CampaignPhase] = {
    CampaignPhase.FREE_PLAY: CampaignPhase.SCORE,
    CampaignPhase.SCORE: CampaignPhase.DOWNTIME,
    CampaignPhase.DOWNTIME: CampaignPhase.FREE_PLAY,
}


class InvalidPhaseTransitionError(EngineError):
    """Raised when a transition skips a step in the free play -> score ->
    downtime -> free play cycle."""


class Session(BaseModel):
    """SPECIFICATION.md §5: "Session/Campaign" - "current phase (free play
    / score / downtime)"."""

    phase: CampaignPhase = CampaignPhase.FREE_PLAY

    def transition_to(self, phase: CampaignPhase) -> "Session":
        expected = _ALLOWED_TRANSITIONS[self.phase]
        if phase is not expected:
            raise InvalidPhaseTransitionError(
                f"cannot go from {self.phase.value!r} to {phase.value!r}; "
                f"expected {expected.value!r}"
            )
        return Session(phase=phase)
