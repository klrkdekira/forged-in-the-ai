from typing import ClassVar

from pydantic import BaseModel

from engine.errors import EngineError

# SRD: "Trauma" > "Trauma Conditions". Matches the `id`s in packs/srd_base.json.
TRAUMA_CONDITIONS = (
    "cold",
    "haunted",
    "obsessed",
    "paranoid",
    "reckless",
    "soft",
    "unstable",
    "vicious",
)


class ArmorAlreadyUsedError(EngineError):
    """Raised when marking an armor box that's already marked (SRD: "Armor"
    - "it can't be used again until it's restored")."""


class StressMarkResult(BaseModel):
    track: "StressTrack"
    triggered_trauma: bool


class StressTrack(BaseModel):
    """SRD: "Stress" / "Trauma" - marking the last (ninth) box triggers
    trauma; the character returns from it at zero stress."""

    MAX: ClassVar[int] = 9
    marked: int = 0

    def mark(self, amount: int) -> StressMarkResult:
        new_marked = max(0, self.marked + amount)
        if new_marked >= self.MAX:
            return StressMarkResult(track=StressTrack(marked=0), triggered_trauma=True)
        return StressMarkResult(track=StressTrack(marked=new_marked), triggered_trauma=False)


class TraumaTrack(BaseModel):
    """SRD: "Trauma" - conditions are permanent; a fourth retires the PC."""

    MAX: ClassVar[int] = 4
    conditions: list[str] = []

    def add(self, condition: str) -> "TraumaTrack":
        return TraumaTrack(conditions=[*self.conditions, condition])

    @property
    def is_retired(self) -> bool:
        return len(self.conditions) >= self.MAX


class HarmEntry(BaseModel):
    level: int
    name: str


class HarmMarkResult(BaseModel):
    track: "HarmTrack"
    catastrophic: bool


class HarmTrack(BaseModel):
    """SRD: "Consequences and Harm" - level 1 and 2 each have two slots,
    level 3 has one; a level that's already full cascades up. Overflowing
    level 3, or being marked with level 4 harm directly, is fatal unless
    resisted (a catastrophic, permanent consequence)."""

    LEVEL_SLOTS: ClassVar[dict[int, int]] = {1: 2, 2: 2, 3: 1}
    entries: list[HarmEntry] = []

    def _count_at(self, level: int) -> int:
        return sum(1 for entry in self.entries if entry.level == level)

    def mark(self, level: int, name: str) -> HarmMarkResult:
        target_level = level
        while target_level in self.LEVEL_SLOTS:
            if self._count_at(target_level) < self.LEVEL_SLOTS[target_level]:
                break
            target_level += 1

        if target_level not in self.LEVEL_SLOTS:
            return HarmMarkResult(track=self, catastrophic=True)

        entries = [*self.entries, HarmEntry(level=target_level, name=name)]
        return HarmMarkResult(track=HarmTrack(entries=entries), catastrophic=False)

    def heal_one_level(self) -> "HarmTrack":
        """SRD: "Recover" - when the healing clock fills, every harm entry
        is reduced by one level; entries reduced below level 1 clear."""
        entries = [
            HarmEntry(level=entry.level - 1, name=entry.name)
            for entry in self.entries
            if entry.level - 1 >= 1
        ]
        return HarmTrack(entries=entries)


class ArmorTrack(BaseModel):
    """SRD: "Armor" / "Special Armor" - three boxes (standard, heavy,
    special); mark one to reduce or avoid a consequence instead of rolling
    to resist. Restored when choosing load for the next score."""

    has_armor: bool = False
    has_heavy_armor: bool = False
    has_special_armor: bool = False
    armor_used: bool = False
    heavy_armor_used: bool = False
    special_armor_used: bool = False

    def use_armor(self) -> "ArmorTrack":
        if not self.has_armor or self.armor_used:
            raise ArmorAlreadyUsedError("armor is unavailable or already used")
        return self.model_copy(update={"armor_used": True})

    def use_heavy_armor(self) -> "ArmorTrack":
        if not self.has_heavy_armor or self.heavy_armor_used:
            raise ArmorAlreadyUsedError("heavy armor is unavailable or already used")
        return self.model_copy(update={"heavy_armor_used": True})

    def use_special_armor(self) -> "ArmorTrack":
        if not self.has_special_armor or self.special_armor_used:
            raise ArmorAlreadyUsedError("special armor is unavailable or already used")
        return self.model_copy(update={"special_armor_used": True})

    def restored(self) -> "ArmorTrack":
        return self.model_copy(
            update={"armor_used": False, "heavy_armor_used": False, "special_armor_used": False}
        )
