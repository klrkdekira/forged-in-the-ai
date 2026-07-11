from engine.campaign import CampaignCanon, SessionZeroConfig


def test_session_zero_config_round_trips_through_json():
    # FR-17: safety tools agreed before play starts.
    config = SessionZeroConfig(lines=["no animal harm"], veils=["torture"], tone="pulpy noir")

    assert SessionZeroConfig.model_validate_json(config.model_dump_json()) == config


def test_campaign_canon_grows_with_new_facts():
    # FR-36: the setting grows during play.
    canon = CampaignCanon(setting_name="Test City")

    grown = canon.with_fact("The docks are controlled by a smuggling ring.")

    assert grown.facts == ["The docks are controlled by a smuggling ring."]
    assert canon.facts == []


def test_campaign_canon_facts_stay_in_order():
    canon = CampaignCanon(setting_name="Test City").with_fact("first").with_fact("second")

    assert canon.facts == ["first", "second"]


def test_campaign_canon_grows_with_new_locations():
    # FR-15: the map grows as new locations are discovered during play.
    canon = CampaignCanon(setting_name="Test City", locations=["The Docks"])

    grown = canon.with_location("The Old Quarter")

    assert grown.locations == ["The Docks", "The Old Quarter"]
    assert canon.locations == ["The Docks"]
