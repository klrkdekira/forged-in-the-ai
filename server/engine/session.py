from enum import StrEnum

from pydantic import BaseModel, Field

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


class DowntimeActivityError(EngineError):
    """Raised when a downtime activity or training slot is unavailable."""


class Session(BaseModel):
    """SPECIFICATION.md §5: "Session/Campaign" - "current phase (free play
    / score / downtime)"."""

    phase: CampaignPhase = CampaignPhase.FREE_PLAY
    downtime_activity_counts: dict[str, int] = Field(default_factory=dict)
    downtime_training_tracks: dict[str, list[str]] = Field(default_factory=dict)
    score_engagement_completed: bool = False
    score_action_completed: bool = False
    score_heat_completed: bool = False
    score_payoff_completed: bool = False
    score_entanglement_completed: bool = False

    def transition_to(self, phase: CampaignPhase) -> "Session":
        expected = _ALLOWED_TRANSITIONS[self.phase]
        if phase is not expected:
            raise InvalidPhaseTransitionError(
                f"cannot go from {self.phase.value!r} to {phase.value!r}; "
                f"expected {expected.value!r}"
            )
        if phase is CampaignPhase.DOWNTIME:
            # SRD: "Downtime" - each PC gets two activities in each downtime.
            return Session(
                phase=phase,
                score_engagement_completed=self.score_engagement_completed,
                score_action_completed=self.score_action_completed,
                score_payoff_completed=self.score_payoff_completed,
                score_entanglement_completed=self.score_entanglement_completed,
                score_heat_completed=self.score_heat_completed,
            )
        return Session(
            phase=phase,
            downtime_activity_counts=self.downtime_activity_counts,
            downtime_training_tracks=self.downtime_training_tracks,
            score_engagement_completed=self.score_engagement_completed,
            score_action_completed=self.score_action_completed,
            score_heat_completed=self.score_heat_completed,
            score_payoff_completed=self.score_payoff_completed,
            score_entanglement_completed=self.score_entanglement_completed,
        )

    def begin_downtime_activity(self, character_id: str, track: str | None = None) -> "Session":
        """SRD: "Downtime Activities" - record one activity and one
        training track for this PC. The caller handles any extra-activity
        payment before committing this returned session."""
        if self.phase is not CampaignPhase.DOWNTIME:
            raise DowntimeActivityError("downtime activities are only available during downtime")
        used = self.downtime_activity_counts.get(character_id, 0)
        tracks = self.downtime_training_tracks.get(character_id, [])
        if track is not None and track in tracks:
            raise DowntimeActivityError(
                f"{character_id!r} has already trained {track!r} this downtime"
            )
        updated_tracks = {**self.downtime_training_tracks}
        if track is not None:
            updated_tracks[character_id] = [*tracks, track]
        return self.model_copy(
            update={
                "downtime_activity_counts": {
                    **self.downtime_activity_counts,
                    character_id: used + 1,
                },
                "downtime_training_tracks": updated_tracks,
            }
        )
