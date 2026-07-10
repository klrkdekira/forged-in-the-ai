import pytest

from engine.session import CampaignPhase, InvalidPhaseTransitionError, Session


def test_session_starts_in_free_play():
    # SRD: "The Game Structure" - "By default, the game is in free play"
    assert Session().phase is CampaignPhase.FREE_PLAY


def test_session_cycles_free_play_score_downtime_free_play():
    # SRD: "The Game Structure" - the full cycle.
    session = Session()

    session = session.transition_to(CampaignPhase.SCORE)
    assert session.phase is CampaignPhase.SCORE

    session = session.transition_to(CampaignPhase.DOWNTIME)
    assert session.phase is CampaignPhase.DOWNTIME

    session = session.transition_to(CampaignPhase.FREE_PLAY)
    assert session.phase is CampaignPhase.FREE_PLAY


def test_session_refuses_to_skip_a_phase():
    session = Session()

    with pytest.raises(InvalidPhaseTransitionError):
        session.transition_to(CampaignPhase.DOWNTIME)


def test_session_refuses_to_transition_to_the_same_phase():
    session = Session()

    with pytest.raises(InvalidPhaseTransitionError):
        session.transition_to(CampaignPhase.FREE_PLAY)
