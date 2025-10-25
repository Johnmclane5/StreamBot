
import base64
import asyncio
import mimetypes
import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pyrogram.errors import ChannelInvalid
from starlette.status import HTTP_404_NOT_FOUND
from fastapi.staticfiles import StaticFiles

from app import get_worker_bot, Bot, cache
from config import MY_DOMAIN, CHUNK_SIZE
from db import files_col

api = FastAPI()
api.mount("/static", StaticFiles(directory="static"), name="static")
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONCURRENCY_LIMIT = 3
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

logger = logging.getLogger(__name__)


def decode_file_link(file_link: str) -> tuple[int, int]:
    try:
        padding = '=' * (-len(file_link) % 4)
        decoded = base64.urlsafe_b64decode(file_link + padding).decode()
        return map(int, decoded.split("_"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file link")


def get_file_properties(message):
    if message.document:
        return message.caption or message.document.file_name, message.document.file_size
    elif message.video:
        return message.caption or message.video.file_name, message.video.file_size
    elif message.audio:
        return message.audio.file_name, message.audio.file_size
    else:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Unsupported file type")


@api.get("/")
async def root():
    return JSONResponse({"message": "👋 Hola Amigo!"})


async def get_file_stream(channel_id, message_id, request: Request):
    worker = get_worker_bot()
    try:
        message = await worker.get_messages(chat_id=channel_id, message_ids=message_id)
    except ChannelInvalid:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Channel not found")
    if not message:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="File not found")

    file_name, file_size = get_file_properties(message)
    range_header = request.headers.get("range")
    start, end = 0, file_size - 1

    if range_header:
        range_value = range_header.strip().split("=")[1]
        start_str, end_str = range_value.split("-")[:2]
        start = int(start_str)
        if end_str:
            end = int(end_str)

    chunk_offset = start // CHUNK_SIZE
    byte_offset_in_chunk = start % CHUNK_SIZE
    bytes_to_send = end - start + 1

    async def media_streamer():
        bytes_sent = 0
        current_chunk_index = chunk_offset
        is_first_chunk = True

        while bytes_sent < bytes_to_send:
            cache_key = f"{channel_id}_{message_id}_{current_chunk_index}"
            chunk = await cache.get(cache_key)

            if chunk is None:
                # Cache miss: Start streaming from the worker
                async with semaphore:
                    stream = worker.stream_media(message, offset=current_chunk_index)
                    try:
                        async for chunk_data in stream:
                            # Cache the new chunk
                            await cache.put(f"{channel_id}_{message_id}_{current_chunk_index}", chunk_data)

                            # Process and yield the chunk
                            if is_first_chunk:
                                chunk = chunk_data[byte_offset_in_chunk:]
                                is_first_chunk = False
                            else:
                                chunk = chunk_data

                            remaining_bytes = bytes_to_send - bytes_sent
                            if len(chunk) > remaining_bytes:
                                chunk = chunk[:remaining_bytes]

                            yield chunk
                            bytes_sent += len(chunk)
                            current_chunk_index += 1

                            if bytes_sent >= bytes_to_send:
                                break
                        # This outer break is to exit the while loop once the stream is exhausted
                        break
                    except StopAsyncIteration:
                        break # Exit if the stream is exhausted
            else:
                # Cache hit: Serve the chunk from the cache
                if is_first_chunk:
                    chunk = chunk[byte_offset_in_chunk:]
                    is_first_chunk = False

                remaining_bytes = bytes_to_send - bytes_sent
                if len(chunk) > remaining_bytes:
                    chunk = chunk[:remaining_bytes]

                yield chunk
                bytes_sent += len(chunk)
                current_chunk_index += 1

    return media_streamer, start, end, file_size, file_name


@api.get("/stream/{file_link}")
@api.head("/stream/{file_link}")
async def stream_file(file_link: str, request: Request):
    channel_id, message_id = decode_file_link(file_link)
    media_streamer, start, end, file_size, file_name = await get_file_stream(channel_id, message_id, request)
    mime_type, _ = mimetypes.guess_type(file_name)
    if mime_type is None:
        mime_type = "video/mp4"

    headers = {
        "Content-Type": mime_type,
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Disposition": f'attachment; filename="{file_name}"'
    }
    return StreamingResponse(media_streamer(), status_code=206 if start > 0 else 200, headers=headers)


@api.get("/download/{file_link}")
async def download_file(file_link: str, request: Request):
    channel_id, message_id = decode_file_link(file_link)
    media_streamer, _, _, file_size, file_name = await get_file_stream(channel_id, message_id, request)
    headers = {
        "Content-Disposition": f"attachment; filename=\"{file_name}\"",
        "Content-Type": "application/octet-stream",
        "Content-Length": str(file_size),
    }
    return StreamingResponse(media_streamer(), headers=headers)


@api.get("/subtitle/{file_link}")
async def serve_subtitle(file_link: str, request: Request):
    channel_id, message_id = decode_file_link(file_link)
    media_streamer, _, _, file_size, _ = await get_file_stream(channel_id, message_id, request)
    headers = {
        "Content-Type": "text/plain",
        "Content-Length": str(file_size),
    }
    return StreamingResponse(media_streamer(), headers=headers)


@api.get("/player/{file_link}")
async def play_video(file_link: str):
    return FileResponse(f"static/player.html")


from utility import human_readable_size

@api.get("/details/{file_link}")
async def get_file_details(file_link: str):
    channel_id, message_id = decode_file_link(file_link)
    worker = get_worker_bot()
    try:
        message = await worker.get_messages(chat_id=channel_id, message_ids=message_id)
    except ChannelInvalid:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Channel not found")
    if not message:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="File not found")

    file_name, file_size = get_file_properties(message)
    mime_type, _ = mimetypes.guess_type(file_name)
    if mime_type is None:
        mime_type = "video/mp4"

    # Subtitle search logic
    subtitle_url = None
    base_name, _ = os.path.splitext(file_name)
    subtitle_name = f"{base_name}.srt"

    subtitle_doc = files_col.find_one({"file_name": subtitle_name})
    if subtitle_doc:
        bot_instance = Bot("temp_instance")
        subtitle_link = bot_instance.encode_file_link(subtitle_doc['channel_id'], subtitle_doc['message_id'])
        subtitle_url = f"/subtitle/{subtitle_link}"

    return JSONResponse({
        "file_name": file_name,
        "file_size": human_readable_size(file_size),
        "mime_type": mime_type,
        "subtitle_url": subtitle_url
    })


@api.get("/play/{player}/{file_link}")
async def play_in_player(player: str, file_link: str):
    stream_url = f"{MY_DOMAIN}/stream/{file_link}"
    if player == "mx":
        redirect_url = f"intent:{stream_url}#Intent;action=android.intent.action.VIEW;type=video/*;package=com.mxtech.videoplayer.ad;end"
    elif player == "mxpro":
        redirect_url = f"intent:{stream_url}#Intent;action=android.intent.action.VIEW;type=video/*;package=com.mxtech.videoplayer.pro;end"
    else:
        raise HTTPException(status_code=404, detail="Player not supported")
    return RedirectResponse(url=redirect_url, status_code=302)
