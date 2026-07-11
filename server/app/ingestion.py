from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ai.llm_client import LLMClient
from app.llm import build_llm_client
from app.settings import Settings, get_settings
from engine.packs import ContentPack
from ingestion.module_extraction import ModuleDraft, extract_module_draft
from ingestion.module_review import finalize_module
from ingestion.text_extraction import UnsupportedFormatError, extract_text
from state.db import app_db_path, make_engine, make_session_factory
from state.module_store import ModuleIdError, list_modules, load_module, save_module
from state.srd_index import chunk_module_prose, index_module_chunks

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


def get_llm_client(settings: Settings = Depends(get_settings)) -> LLMClient:
    """Same construction as `app.session_ws`'s dependency (ADR-0001), but
    refuses with an HTTP-appropriate error - this router has no WebSocket
    connection to close instead."""
    client = build_llm_client(settings)
    if client is None:
        raise HTTPException(status_code=503, detail="LLM_BASE_URL/LLM_MODEL not configured")
    return client


class ExtractedText(BaseModel):
    filename: str
    text: str
    char_count: int


class ExtractModuleRequest(BaseModel):
    text: str


class ExtractModuleResponse(BaseModel):
    draft: ModuleDraft
    truncated: bool = Field(
        description="True if the source text was cut to fit the extraction budget"
    )


class FinalizeModuleRequest(BaseModel):
    id: str
    name: str
    description: str
    version: str
    draft: ModuleDraft = Field(
        description="The reviewed/edited draft - whatever the user changed since /extract-module"
    )


class ModuleSummary(BaseModel):
    id: str
    name: str
    description: str
    version: str


class SaveModuleRequest(BaseModel):
    pack: ContentPack
    source_text: str | None = Field(
        None,
        description="The module's normalised source text (FR-21) - indexed for GM retrieval "
        "(FR-24) alongside the SRD if given; the saved pack itself is unaffected either way",
    )


@router.post("/extract-text", response_model=ExtractedText)
async def extract_uploaded_text(file: UploadFile) -> ExtractedText:
    """FR-21: the rulebook ingestion pipeline's first step (Phase 6) - a
    user's uploaded PDF/markdown/plain text file, reduced to normalised
    plain text. Returned to the caller rather than persisted: FR-22's
    LLM-assisted structuring and FR-23's private-module storage are their
    own later steps, not this one's job."""
    if file.filename is None:
        raise HTTPException(status_code=400, detail="uploaded file has no filename")

    content = await file.read()
    try:
        text = extract_text(file.filename, content)
    except UnsupportedFormatError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return ExtractedText(filename=file.filename, text=text, char_count=len(text))


@router.post("/extract-module", response_model=ExtractModuleResponse)
async def extract_module(
    body: ExtractModuleRequest, client: LLMClient = Depends(get_llm_client)
) -> ExtractModuleResponse:
    """FR-22: the ingestion pipeline's second step - FR-21's normalised
    text, LLM-structured into a best-effort `ModuleDraft` (FR-9's
    content-pack shapes). Takes already-extracted text (from
    `/extract-text`) rather than a re-upload, keeping the two steps
    independently callable. The result is returned, not persisted or
    activated in any campaign - the review/edit step and FR-23's private
    storage are their own, later steps."""
    result = await extract_module_draft(client, body.text)
    return ExtractModuleResponse(draft=result.draft, truncated=result.truncated)


@router.post("/finalize-module", response_model=ContentPack)
async def finalize_module_endpoint(body: FinalizeModuleRequest) -> ContentPack:
    """FR-22: the review/edit step's validation boundary - a reviewed/
    edited draft becomes a real `ContentPack` (FR-9) once it validates
    here (an edit that no longer matches `ModuleDraft`'s schema is
    already refused by FastAPI/pydantic before this body ever runs,
    CLAUDE.md's "the engine may refuse; it never guesses"). Returned to
    the caller, not persisted or associated with any campaign: FR-23's
    private-module storage is the next, separate step. No licensing
    check here or on save: a private module is the user's own local
    data (NOTICE.md, C6) - the firewall guards distribution surfaces
    (commits, the committed `packs/`), not what stays on the user's
    machine."""
    return finalize_module(
        body.draft,
        pack_id=body.id,
        name=body.name,
        description=body.description,
        version=body.version,
    )


@router.post("/modules", response_model=ContentPack)
async def save_module_endpoint(
    body: SaveModuleRequest, settings: Settings = Depends(get_settings)
) -> ContentPack:
    """FR-23/C6: private-module storage - a finalized module (typically
    `/finalize-module`'s own response, re-posted here once the user is
    happy with it) saved under the user's data directory, never the
    repo's committed `packs/` (`state/module_store.py`). Re-saving an
    existing id overwrites it - there's no separate "update" verb, same
    as `/api/campaigns` has none for its own snapshot overwrites.

    FR-24: if `source_text` is given, it's chunked and indexed into the
    same retrieval corpus the SRD lives in (`state/srd_index.py`) under
    this module's own source tag - the GM agent's live retrieval
    (`ai/agent.py`) then ranks it alongside the SRD on later turns."""
    try:
        save_module(settings.data_dir, body.pack)
    except ModuleIdError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if body.source_text:
        engine = make_engine(app_db_path(settings.data_dir))
        try:
            async with make_session_factory(engine)() as session:
                chunks = chunk_module_prose(body.pack.id, body.source_text)
                await index_module_chunks(session, body.pack.id, chunks)
        finally:
            await engine.dispose()

    return body.pack


@router.get("/modules", response_model=list[ModuleSummary])
async def list_modules_endpoint(settings: Settings = Depends(get_settings)) -> list[ModuleSummary]:
    """FR-23: every private module currently saved - summaries only
    (CLAUDE.md's schema-is-the-contract habit already does this for
    `CampaignSummary`), since a module's full content can be sizeable and
    the caller usually just wants to know what's available."""
    return [
        ModuleSummary.model_validate(pack.model_dump()) for pack in list_modules(settings.data_dir)
    ]


@router.get("/modules/{module_id}", response_model=ContentPack)
async def get_module_endpoint(
    module_id: str, settings: Settings = Depends(get_settings)
) -> ContentPack:
    try:
        pack = load_module(settings.data_dir, module_id)
    except ModuleIdError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if pack is None:
        raise HTTPException(status_code=404, detail=f"unknown module {module_id!r}")
    return pack
