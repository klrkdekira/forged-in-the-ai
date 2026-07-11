from pathlib import Path

from ai.procedures import PROCEDURES, SESSION_ZERO_PROCEDURE
from ai.system_prompt import build_system_prompt
from engine.pack_loader import load_pack

PACK_PATH = Path(__file__).parents[2] / "packs" / "srd_base.json"


def test_every_procedure_citation_is_a_real_srd_heading():
    # NFR-2: citations are checked against the actual committed SRD section
    # index, not just asserted - a renamed/removed heading fails this.
    pack = load_pack(PACK_PATH)
    headings = {section.heading for section in pack.srd_sections}

    for procedure in PROCEDURES:
        for heading in procedure.srd_sections:
            assert heading in headings, f"{heading!r} not found in the SRD section index"


def test_build_system_prompt_includes_every_procedure():
    prompt = build_system_prompt()

    for procedure in PROCEDURES:
        assert procedure.title in prompt
        assert procedure.text in prompt


def test_build_system_prompt_states_the_engine_adjudicates_principle():
    # CLAUDE.md: "The engine adjudicates, the model narrates."
    assert "tool call" in build_system_prompt()


def test_build_system_prompt_includes_session_zero_only_when_needed():
    # FR-17/FR-36: session zero isn't unconditional like PROCEDURES - it
    # should disappear once a campaign has completed it, or every turn
    # after would re-run the interview.
    assert SESSION_ZERO_PROCEDURE.title in build_system_prompt(needs_session_zero=True)
    assert SESSION_ZERO_PROCEDURE.title not in build_system_prompt(needs_session_zero=False)
    assert SESSION_ZERO_PROCEDURE.title not in build_system_prompt()
