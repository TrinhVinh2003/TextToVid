from typing import Any, Optional

from pydantic import BaseModel


class VideoScriptParams:
    """
    {
      "video_subject": "Spring Flower Sea",
      "video_language": "",
      "paragraph_number": 1
    }.
    """  # noqa: D205

    video_subject: Optional[str] = "Spring Flower Sea"
    video_language: Optional[str] = ""
    paragraph_number: Optional[int] = 1


class VideoTermsParams:
    """
    {
      "video_subject": "",
      "video_script": "",
      "amount": 5
    }
    """

    video_subject: Optional[str] = "Spring Flower Sea"
    video_script: Optional[str] = (
        "The sea of flowers in spring unfolds like a poem and a painting before your eyes. In the season of rebirth, the earth dons a splendid, colorful attire. Golden forsythia, pink cherry blossoms, pure white pear flowers, bright tulips..."
    )
    amount: Optional[int] = 5


class VideoScriptRequest(VideoScriptParams, BaseModel):
    pass


class VideoTermsRequest(VideoTermsParams, BaseModel):
    pass

class BaseResponse(BaseModel):
    status: int = 200
    message: Optional[str] = "success"
    data: Any = None

class VideoScriptResponse(BaseResponse):
    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "video_script": "春天的花海，是大自然的一幅美丽画卷。在这个季节里，大地复苏，万物生长，花朵争相绽放，形成了一片五彩斑斓的花海..."
                },
            },
        }


class VideoTermsResponse(BaseResponse):
    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {"video_terms": ["sky", "tree"]},
            },
        }

