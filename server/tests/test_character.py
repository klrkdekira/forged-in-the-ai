from engine.character import Action, Attribute, Character, attribute_rating, render_markdown


def test_attribute_rating_counts_actions_with_at_least_one_dot():
    # SRD: "EXAMPLE ACTION & ATTRIBUTE RATINGS" - Insight example: Hunt 1,
    # Study/Survey/Tinker 0 -> "Insight attribute rating is 1".
    ratings = {Action.HUNT: 1, Action.STUDY: 0, Action.SURVEY: 0, Action.TINKER: 0}

    assert attribute_rating(ratings, Attribute.INSIGHT) == 1


def test_attribute_rating_counts_actions_not_dots():
    # SRD: same section - Prowess example: Prowl 1, Skirmish 2 (others 0)
    # -> "Prowess attribute rating is 2" (two actions with dots, not three).
    ratings = {
        Action.FINESSE: 0,
        Action.PROWL: 1,
        Action.SKIRMISH: 2,
        Action.WRECK: 0,
    }

    assert attribute_rating(ratings, Attribute.PROWESS) == 2


def test_character_computes_its_own_attribute_ratings():
    character = Character(
        name="Test",
        playbook="Test Playbook",
        action_ratings={Action.ATTUNE: 2, Action.COMMAND: 1, Action.SWAY: 1},
    )

    assert character.attribute_rating(Attribute.RESOLVE) == 3


def test_character_json_round_trips():
    # FR-8: JSON import/export.
    character = Character(name="Test", playbook="Test Playbook", coin=3)

    restored = Character.model_validate_json(character.model_dump_json())

    assert restored == character


def test_render_markdown_includes_name_and_playbook():
    # FR-8: human-readable markdown sheet render.
    character = Character(name="Test", playbook="Test Playbook")

    markdown = render_markdown(character)

    assert "# Test" in markdown
    assert "Test Playbook" in markdown
