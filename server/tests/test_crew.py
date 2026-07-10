from engine.crew import Claim, Cohort, Crew, render_markdown
from engine.crew_mechanics import Hold


def test_crew_defaults_to_tier_zero_strong_hold():
    # SRD: "Hold" - "Your crew begins with strong hold at Tier 0."
    crew = Crew(name="Test Crew", crew_type="Test Type")

    assert crew.tier == 0
    assert crew.hold is Hold.STRONG


def test_crew_json_round_trips():
    # FR-8: JSON import/export.
    crew = Crew(
        name="Test Crew",
        crew_type="Test Type",
        claims=[Claim(id="dock", name="The Dock", controlled=True)],
        cohorts=[Cohort(types=["Thugs"], quality=1, scale=1)],
    )

    restored = Crew.model_validate_json(crew.model_dump_json())

    assert restored == crew


def test_render_markdown_includes_name_and_tier():
    # FR-8: human-readable markdown sheet render.
    crew = Crew(name="Test Crew", crew_type="Test Type", tier=2)

    markdown = render_markdown(crew)

    assert "# Test Crew" in markdown
    assert "Tier**: 2" in markdown
