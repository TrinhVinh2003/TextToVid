from fastapi import Request
from fastapi.routing import APIRouter

from app.repositories.gen_text.generate_text import generate_script, generate_terms
from app.utils import utils
from app.web.api.gen_text.schema import (
    VideoScriptRequest,
    VideoScriptResponse,
    VideoTermsRequest,
    VideoTermsResponse,
)

router = APIRouter()


@router.post(
    "/scripts",
    response_model=VideoScriptResponse,
    summary="Create a script for the video",
)
def generate_video_script(request: Request, body: VideoScriptRequest):
    """
    API endpoint to generate a video script.
    Takes video subject, language, and paragraph number as input and generates a corresponding script.
    """  # noqa: D205

    video_script = generate_script(
        video_subject=body.video_subject,
        language=body.video_language,
        paragraph_number=body.paragraph_number,
    )
    response = {"video_script": video_script}
    return utils.get_response(200, response)


@router.post(
    "/terms",
    response_model=VideoTermsResponse,
    summary="Generate video terms based on the video script",
)
def generate_video_terms(request: Request, body: VideoTermsRequest):
    """
    API endpoint to generate video terms based on the script.
    Takes video subject, script, and term amount as input and generates relevant video terms.
    """  # noqa: D205, E501

    video_terms = generate_terms(
        video_subject=body.video_subject,
        video_script=body.video_script,
        amount=body.amount,
    )
    response = {"video_terms": video_terms}
    return utils.get_response(200, response)
