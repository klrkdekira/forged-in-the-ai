from pydantic import BaseModel, Field

from engine.errors import EngineError


class ControllerError(EngineError):
    """Raised when a seat is assigned a character/cohort it doesn't
    control, or a character/cohort is claimed by more than one seat."""


class Controller(BaseModel):
    """FR-25: one human seat, controlling any number of PCs and cohorts.
    Solo play (single-player MVP) is one Controller whose character_ids
    covers the whole crew - not a special case, just this with one seat."""

    seat_id: str
    character_ids: list[str] = Field(default_factory=list)
    cohort_ids: list[str] = Field(default_factory=list)

    def controls(self, character_id: str) -> bool:
        return character_id in self.character_ids


def solo_controller(seat_id: str, character_ids: list[str], cohort_ids: list[str]) -> Controller:
    """FR-25: "solo play is the whole crew under one seat" - construct the
    single-seat controller for every PC/cohort in the crew."""
    return Controller(seat_id=seat_id, character_ids=character_ids, cohort_ids=cohort_ids)


def assert_controls(controllers: list[Controller], seat_id: str, character_id: str) -> None:
    """Refuses an action attempted for a character the acting seat doesn't
    control, rather than guessing which seat "should" be allowed."""
    seat = next((c for c in controllers if c.seat_id == seat_id), None)
    if seat is None or not seat.controls(character_id):
        raise ControllerError(f"seat {seat_id!r} does not control character {character_id!r}")


def assert_no_double_assignment(controllers: list[Controller]) -> None:
    """Refuses a controller layout where two seats claim the same PC."""
    seen: dict[str, str] = {}
    for controller in controllers:
        for character_id in controller.character_ids:
            if character_id in seen and seen[character_id] != controller.seat_id:
                raise ControllerError(
                    f"character {character_id!r} is assigned to both "
                    f"{seen[character_id]!r} and {controller.seat_id!r}"
                )
            seen[character_id] = controller.seat_id
