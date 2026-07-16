import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notice", tags=["notice"])

_MISSING_NOTICE = (
    "NOTICE.md is not available in this deployment. See the project's own "
    "NOTICE.md for the required Blades in the Dark SRD (CC-BY 3.0) attribution."
)


class NoticeResponse(BaseModel):
    text: str


@router.get("", response_model=NoticeResponse)
def get_notice(settings: Settings = Depends(get_settings)) -> NoticeResponse:
    """C1: the CC-BY attribution text must appear in any distributed UI's
    credits. Serves NOTICE.md's actual content, verbatim, rather than a
    hand-copied constant - nothing to keep in sync if NOTICE.md changes."""
    try:
        text = settings.notice_path.read_text()
    except OSError as error:
        logger.warning("could not read NOTICE.md from %s: %s", settings.notice_path, error)
        text = _MISSING_NOTICE
    return NoticeResponse(text=text)
