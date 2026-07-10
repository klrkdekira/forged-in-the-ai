from engine.crew_mechanics import CohortHarmLevel, CohortHarmTrack, HeatTrack, RepTrack


def test_heat_below_max_does_not_increase_wanted_level():
    # SRD: "Heat" - "when your heat level reaches 9, you gain a wanted level"
    result = HeatTrack(heat=5).add(3)

    assert result.track.heat == 8
    assert not result.wanted_level_increased


def test_heat_overflow_rolls_over_and_increases_wanted_level():
    # SRD: "Heat" - "if your heat was 7 and you took 4 heat, you'd reset
    # with 2 heat marked"
    result = HeatTrack(heat=7).add(4)

    assert result.wanted_level_increased
    assert result.track.heat == 2


def test_rep_threshold_is_reduced_by_turf():
    # SRD: "Turf" - "if you have 2 turf, you need 10 rep to develop"
    rep = RepTrack(turf=2)

    assert rep.threshold == 10


def test_rep_threshold_floors_at_six_turf():
    rep = RepTrack(turf=6)

    assert rep.threshold == 6


def test_ready_to_develop_once_rep_reaches_threshold():
    rep = RepTrack(turf=2).add_rep(10)

    assert rep.ready_to_develop


def test_developed_clears_rep_but_keeps_turf():
    # SRD: "Development" - "you'll clear the Rep marks, but keep the turf marks"
    rep = RepTrack(rep=10, turf=2).developed()

    assert rep.rep == 0
    assert rep.turf == 2


def test_cohort_harm_progresses_through_named_levels():
    # SRD: "Cohort harm & Healing" - "four levels of harm"
    harm = CohortHarmTrack().mark().mark()

    assert harm.level == CohortHarmLevel.IMPAIRED


def test_cohort_harm_caps_at_dead():
    harm = CohortHarmTrack().mark(10)

    assert harm.level == CohortHarmLevel.DEAD


def test_cohort_harm_heals():
    harm = CohortHarmTrack(level=CohortHarmLevel.BROKEN).heal()

    assert harm.level == CohortHarmLevel.IMPAIRED
