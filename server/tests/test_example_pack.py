from pathlib import Path

from cli.example_pack import build_pack
from engine.pack_loader import load_pack

PACK_PATH = Path(__file__).parents[2] / "packs" / "example_base.json"


def test_example_pack_matches_the_build_function():
    # FR-9: proves the content-pack format with one original playbook and
    # one original crew type (`make build-example-pack` regenerates it).
    assert build_pack() == load_pack(PACK_PATH)


def test_example_pack_has_no_real_bitd_playbook_or_crew_type_names():
    # C3/C4: never a real Blades in the Dark playbook/crew-type assembly.
    real_playbooks = {"cutter", "hound", "leech", "lurk", "slide", "spider", "whisper"}
    real_crew_types = {"assassins", "bravos", "cult", "hawkers", "shadows", "smugglers"}
    pack = build_pack()

    assert not {p.name.lower() for p in pack.playbooks} & real_playbooks
    assert not {c.name.lower() for c in pack.crew_types} & real_crew_types


def test_example_pack_loads_through_the_licensing_firewall():
    pack = load_pack(PACK_PATH)

    assert pack.playbooks[0].name == "Wayfarer"
    assert pack.crew_types[0].name == "Couriers"
