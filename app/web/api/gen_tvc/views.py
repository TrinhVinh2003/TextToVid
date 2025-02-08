import glob
import os
import pathlib
import shutil
from typing import Union

from fastapi import BackgroundTasks, Depends, Path, Request, UploadFile
from fastapi.params import File
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.routing import APIRouter
from loguru import logger

from app.core.settings import settings
from app.repositories.gen_tvc import task as tm
from app.web.api.gen_tvc.schemas import (
    AudioRequest,
    BgmRetrieveResponse,
    BgmUploadResponse,
    SubtitleRequest,
    TaskDeletionResponse,
    TaskQueryRequest,
    TaskQueryResponse,
    TaskResponse,
    TaskVideoRequest,
)
from app.services.manager import state as sm
from app.services.manager.memory_manager import InMemoryTaskManager
from app.services.manager.redis_manager import RedisTaskManager
from app.utils import string_utils, utils
from app.web.exception import HttpException

router = APIRouter()

# Configuration settings for Redis and max concurrent tasks
_enable_redis = settings.enable_redis
_redis_host = settings.redis_host
_redis_port = settings.redis_port
_redis_db = settings.redis_db
_redis_password = settings.redis_password
_max_concurrent_tasks = settings.max_concurrent_tasks

redis_url = f"redis://:{_redis_password}@{_redis_host}:{_redis_port}/{_redis_db}"

# Initialize the task manager based on Redis or in-memory storage
if _enable_redis:
    task_manager = RedisTaskManager(
        max_concurrent_tasks=_max_concurrent_tasks, redis_url=redis_url
    )
else:
    task_manager = InMemoryTaskManager(max_concurrent_tasks=_max_concurrent_tasks)


@router.post("/videos", response_model=TaskResponse, summary="Generate a short video")
def create_video(
    background_tasks: BackgroundTasks,
    request: Request,
    body: TaskVideoRequest,
) -> TaskResponse:
    """
    Endpoint to create a short video based on provided request data.

    Args:
        background_tasks (BackgroundTasks): Background task for async processing.
        request (Request): The incoming request.
        body (TaskVideoRequest): The request body containing video generation parameters.

    Returns:
        TaskResponse: The response containing task status and generated video data.
    """
    return create_task(request, body, stop_at="video")


@router.post("/subtitle", response_model=TaskResponse, summary="Generate subtitle only")
def create_subtitle(
    background_tasks: BackgroundTasks, request: Request, body: SubtitleRequest
) -> TaskResponse:
    """
    Endpoint to create subtitles for a video.

    Args:
        background_tasks (BackgroundTasks): Background task for async processing.
        request (Request): The incoming request.
        body (SubtitleRequest): The request body containing subtitle generation parameters.

    Returns:
        TaskResponse: The response containing task status and subtitle data.
    """
    return create_task(request, body, stop_at="subtitle")


@router.post("/audio", response_model=TaskResponse, summary="Generate audio only")
def create_audio(
    background_tasks: BackgroundTasks,
    request: Request,
    body: AudioRequest,
) -> TaskResponse:
    """
    Endpoint to generate audio based on provided request data.

    Args:
        background_tasks (BackgroundTasks): Background task for async processing.
        request (Request): The incoming request.
        body (AudioRequest): The request body containing audio generation parameters.

    Returns:
        TaskResponse: The response containing task status and audio data.
    """
    return create_task(request, body, stop_at="audio")


def create_task(
    request: Request,
    body: Union[TaskVideoRequest, SubtitleRequest, AudioRequest],
    stop_at: str,
) -> dict[str, int]:
    """
    Helper function to initiate task creation for video, subtitle, or audio processing.

    Args:
        request (Request): The incoming request.
        body (Union[TaskVideoRequest, SubtitleRequest, AudioRequest]): The request body
        with processing parameters.
        stop_at (str): The specific step to stop at (either "video", "subtitle", or
        "audio").

    Returns:
        TaskResponse: The response containing task status and generated data.
    """
    task_id = utils.get_uuid()
    request_id = utils.get_task_id(request)
    try:
        task = {
            "task_id": task_id,
            "request_id": request_id,
            "params": body.model_dump(),
        }
        sm.state.update_task(task_id)
        task_manager.add_task(tm.start, task_id=task_id, params=body, stop_at=stop_at)
        logger.success(f"Task created: {string_utils.to_json(task)}")
        return utils.get_response(200, task)
    except ValueError as e:
        raise HttpException(
            task_id=task_id,
            status_code=400,
            message=f"{request_id}: {e!s}",
        ) from e


@router.get(
    "/tasks/{task_id}", response_model=TaskQueryResponse, summary="Query task status"
)
def get_task(
    request: Request,
    task_id: str = Path(..., description="Task ID"),
    query: TaskQueryRequest = Depends(),
) -> TaskQueryResponse:
    """
    Endpoint to query the status of a specific task.

    Args:
        request (Request): The incoming request.
        task_id (str): The ID of the task to query.
        query (TaskQueryRequest): The query parameters for the task.

    Returns:
        TaskQueryResponse: The response containing task status information.
    """
    endpoint = ""
    if not endpoint:
        endpoint = str(request.base_url)
    endpoint = endpoint.rstrip("/")

    request_id = utils.get_task_id(request)
    task = sm.state.get_task(task_id)
    if task:
        task_dir = utils.task_dir()

        def file_to_uri(file: str) -> str:
            if not file.startswith(endpoint):
                _uri_path = v.replace(task_dir, "tasks").replace("\\", "/")
                _uri_path = f"{endpoint}/{_uri_path}"
            else:
                _uri_path = file
            return _uri_path

        if "videos" in task:
            videos = task["videos"]
            urls = []
            for v in videos:
                urls.append(file_to_uri(v))
            task["videos"] = urls
        if "combined_videos" in task:
            combined_videos = task["combined_videos"]
            urls = []
            for v in combined_videos:
                urls.append(file_to_uri(v))
            task["combined_videos"] = urls
        return utils.get_response(200, task)

    raise HttpException(
        task_id=task_id, status_code=404, message=f"{request_id}: task not found"
    )


@router.delete(
    "/tasks/{task_id}",
    response_model=TaskDeletionResponse,
    summary="Delete a generated short video task",
)
def delete_video(
    request: Request, task_id: str = Path(..., description="Task ID")
) -> TaskDeletionResponse:
    """
    Endpoint to delete a generated video task and its associated files.

    Args:
        request (Request): The incoming request.
        task_id (str): The ID of the task to delete.

    Returns:
        TaskDeletionResponse: The response confirming the deletion of the task.
    """
    request_id = utils.get_task_id(request)
    task = sm.state.get_task(task_id)
    if task:
        tasks_dir = utils.task_dir()
        current_task_dir = os.path.join(tasks_dir, task_id)
        if os.path.exists(current_task_dir):  # noqa: PTH110
            shutil.rmtree(current_task_dir)

        sm.state.delete_task(task_id)
        logger.success(f"video deleted: {string_utils.to_json(task)}")
        return utils.get_response(200)

    raise HttpException(
        task_id=task_id, status_code=404, message=f"{request_id}: task not found"
    )


@router.get(
    "/musics", response_model=BgmRetrieveResponse, summary="Retrieve local BGM files"
)
def get_bgm_list(request: Request) -> BgmRetrieveResponse:
    """
    Endpoint to retrieve a list of available background music (BGM) files.

    Args:
        request (Request): The incoming request.

    Returns:
        BgmRetrieveResponse: The response containing the list of BGM files.
    """
    suffix = "*.mp3"
    song_dir = utils.song_dir()
    files = glob.glob(os.path.join(song_dir, suffix))  # noqa: PTH207
    bgm_list = []
    for file in files:
        bgm_list.append(
            {
                "name": os.path.basename(file),
                "size": os.path.getsize(file),
                "file": file,
            }
        )
    response = {"files": bgm_list}
    return utils.get_response(200, response)


@router.post(
    "/musics",
    response_model=BgmUploadResponse,
    summary="Upload the BGM file to the songs directory",
)
def upload_bgm_file(
    request: Request,
    file: UploadFile = File(...),
) -> BgmUploadResponse:
    """
    Endpoint to upload a background music (BGM) file to the server.

    Args:
        request (Request): The incoming request.
        file (UploadFile): The BGM file to upload.

    Returns:
        BgmUploadResponse: The response containing the uploaded file information.
    """
    request_id = utils.get_task_id(request)
    # check file ext
    if file.filename.endswith("mp3"):
        song_dir = utils.song_dir()
        save_path = os.path.join(song_dir, file.filename)
        # save file
        with open(save_path, "wb+") as buffer:
            # If the file already exists, it will be overwritten
            file.file.seek(0)
            buffer.write(file.file.read())
        response = {"file": save_path}
        return utils.get_response(200, response)

    raise HttpException(
        "",
        status_code=400,
        message=f"{request_id}: Only *.mp3 files can be uploaded",
    )


@router.get("/stream/{file_path:path}")
async def stream_video(
    request: Request,
    file_path: str,
) -> StreamingResponse:
    """
    Endpoint to stream a video file in chunks.

    Args:
        request (Request): The incoming request.
        file_path (str): The path to the video file to stream.

    Returns:
        StreamingResponse: The streaming response for the video file.
    """
    tasks_dir = utils.task_dir()
    video_path = os.path.join(tasks_dir, file_path)
    range_header = request.headers.get("Range")
    video_size = os.path.getsize(video_path)
    start, end = 0, video_size - 1

    length = video_size
    if range_header:
        range_ = range_header.split("bytes=")[1]
        start, end = [int(part) if part else None for part in range_.split("-")]
        if start is None:
            start = video_size - end
            end = video_size - 1
        if end is None:
            end = video_size - 1
        length = end - start + 1

    def file_iterator(file_path: str, offset: int = 0, bytes_to_read=None):
        with open(file_path, "rb") as f:
            f.seek(offset, os.SEEK_SET)
            remaining = bytes_to_read or video_size
            while remaining > 0:
                bytes_to_read = min(4096, remaining)
                data = f.read(bytes_to_read)
                if not data:
                    break
                remaining -= len(data)
                yield data

    response = StreamingResponse(
        file_iterator(video_path, start, length), media_type="video/mp4"
    )
    response.headers["Content-Range"] = f"bytes {start}-{end}/{video_size}"
    response.headers["Accept-Ranges"] = "bytes"
    response.headers["Content-Length"] = str(length)
    response.status_code = 206  # Partial Content

    return response


@router.get("/download/{file_path:path}")
async def download_video(_: Request, file_path: str) -> FileResponse:
    """
    Endpoint to download a video file.

    Args:
        _ (Request): The incoming request.
        file_path (str): The path to the video file to download.

    Returns:
        FileResponse: The response containing the video file for download.
    """
    tasks_dir = utils.task_dir()
    video_path = os.path.join(tasks_dir, file_path)
    file_path = pathlib.Path(video_path)
    filename = file_path.stem
    extension = file_path.suffix
    headers = {"Content-Disposition": f"attachment; filename={filename}{extension}"}
    return FileResponse(
        path=video_path,
        headers=headers,
        filename=f"{filename}{extension}",
        media_type=f"video/{extension[1:]}",
    )
