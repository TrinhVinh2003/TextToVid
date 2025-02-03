from fastapi.responses import StreamingResponse
from fastapi.routing import APIRouter

from app.schemas.request_schema import GenerateTextRequest
from app.utils.api_utils import make_response
from app.web.api import gen_text, gen_tvc

api_router = APIRouter()

api_router.include_router(gen_text.router,prefix="/gen_text",tags = ["gen_text"])
api_router.include_router(gen_tvc.router,prefix="/gen_tvc",tags=["gen_tvc"])

@api_router.post("/generate_text")
async def generate_text(request: GenerateTextRequest) -> StreamingResponse:
    """Test generator text response."""

    text = request.input_text
    generated_text = generate_text(text)
    return make_response(content=generated_text)
