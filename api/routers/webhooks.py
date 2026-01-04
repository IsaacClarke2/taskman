"""
Webhooks router - Telegram webhook handling.
"""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from api.config import get_settings
from api.dependencies import DatabaseSession
from api.models.requests import ParseRequest
from api.models.responses import ParsedContentResponse
from api.services.parser import parse_message, transcribe_voice

logger = logging.getLogger(__name__)
router = APIRouter()

settings = get_settings()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    session: DatabaseSession,
):
    """
    Handle incoming Telegram webhook updates.

    This endpoint receives updates from Telegram and processes them.
    In production, this is called by the Telegram Bot API.
    """
    # Verify webhook secret if configured
    if settings.telegram_webhook_secret:
        secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret_header != settings.telegram_webhook_secret:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook secret",
            )

    # Parse update
    try:
        update = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook update: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON",
        )

    logger.info(f"Received webhook update: {update.get('update_id')}")

    # Process update
    # Note: In the actual implementation, the bot service handles this
    # This endpoint just receives the webhook and can forward to internal processing

    return {"ok": True}


@router.post("/parse", response_model=ParsedContentResponse)
async def parse_user_message(
    request: ParseRequest,
    session: DatabaseSession,
):
    """
    Parse a user message to extract event/note information.

    This endpoint is called by the bot service after receiving a message.
    """
    logger.info(f"Parsing message of type: {request.message_type}")

    result = await parse_message(
        text=request.content,
        user_timezone=request.user_timezone,
        forwarded_from=request.forwarded_from,
    )

    return result


@router.post("/transcribe")
async def transcribe_voice_message(
    request: Request,
):
    """
    Transcribe a voice message.

    Accepts raw audio bytes and returns transcribed text.
    """
    content_type = request.headers.get("content-type", "")
    if "audio" not in content_type and "octet-stream" not in content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected audio content",
        )

    audio_bytes = await request.body()
    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio file",
        )

    # Get filename from header if provided
    filename = request.headers.get("X-Filename", "audio.oga")

    text = await transcribe_voice(audio_bytes, filename)

    return {"text": text}
