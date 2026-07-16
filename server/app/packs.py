import logging

from app.settings import Settings
from engine.pack_loader import PackLoadError, load_pack
from engine.packs import EntanglementEntry

logger = logging.getLogger(__name__)


def load_entanglements(settings: Settings) -> list[EntanglementEntry]:
    """SRD: "Entanglements" - the roll needs the SRD base pack's table.
    Degrades to an empty list (roll_entanglement then refuses with a clear
    error, rather than the WS connection failing to even open) if the pack
    is missing or malformed - the same "missing backend, not a crashed
    turn" shape as GmAgent._retrieve's no-op degrade."""
    path = settings.packs_dir / "srd_base.json"
    try:
        return load_pack(path).entanglements
    except PackLoadError as error:
        logger.warning("could not load the entanglement table from %s: %s", path, error)
        return []
