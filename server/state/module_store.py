import os
import tempfile
from pathlib import Path

from engine.pack_loader import load_pack, load_packs_dir
from engine.packs import ContentPack


class ModuleIdError(ValueError):
    """`pack_id` becomes a filename component (`<pack_id>.json`) - refused
    if it isn't safe to use as one, rather than guessing at what the
    caller meant (CLAUDE.md), since this value can come straight from an
    HTTP request body."""


def modules_dir(data_dir: Path) -> Path:
    """FR-23/C6: private modules live under the user's own data directory
    (ADR-0005), never under the repo's committed `packs/` - a separate
    root from the start, not a filter applied later."""
    return data_dir / "modules"


def _validate_pack_id(pack_id: str) -> None:
    if not pack_id or pack_id in (".", "..") or "/" in pack_id or "\\" in pack_id:
        raise ModuleIdError(f"invalid module id {pack_id!r}")


def module_path(data_dir: Path, pack_id: str) -> Path:
    """Return a validated private-module file path."""
    _validate_pack_id(pack_id)
    return modules_dir(data_dir) / f"{pack_id}.json"


def save_module(data_dir: Path, pack: ContentPack) -> Path:
    """FR-23: persists a finalized module (`ingestion.module_review.
    finalize_module`'s output, typically) as its own private pack file -
    excluded from the repo by the same `server/data/`-style gitignore
    every other user-data path already relies on (ADR-0005), and from
    campaign exports/sharing simply because nothing in those paths reads
    from this directory."""
    directory = modules_dir(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = module_path(data_dir, pack.id)
    payload = pack.model_dump_json(indent=2).encode("utf-8")
    _atomic_write(path, payload)
    return path


def restore_module_bytes(data_dir: Path, pack_id: str, payload: bytes) -> Path:
    """Restore a previously saved file after a later index operation fails."""
    directory = modules_dir(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = module_path(data_dir, pack_id)
    _atomic_write(path, payload)
    return path


def _atomic_write(path: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(payload)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def load_module(data_dir: Path, pack_id: str) -> ContentPack | None:
    """None for an unknown id - a missing module is a normal case here
    (the caller looked one up that was never saved, or was deleted
    outside this process), not the same as a corrupt pack file existing
    on disk, which `load_pack` still refuses to load. Loaded as private
    (NOTICE.md: owners may keep core-book content in their own modules;
    the licensing firewall guards distribution, not user data)."""
    path = module_path(data_dir, pack_id)
    if not path.exists():
        return None
    return load_pack(path, private=True)


def list_modules(data_dir: Path) -> list[ContentPack]:
    """Every private module currently saved, filename order (same
    contract as `load_packs_dir` for the committed `packs/` directory,
    but private - see `load_module`)."""
    directory = modules_dir(data_dir)
    if not directory.exists():
        return []
    return load_packs_dir(directory, private=True)


def delete_module(data_dir: Path, pack_id: str) -> bool:
    """FR-23: deletes a saved private module file. Returns True if the
    file existed and was deleted, False if it was already absent."""
    path = module_path(data_dir, pack_id)
    if not path.exists():
        return False
    path.unlink()
    return True
