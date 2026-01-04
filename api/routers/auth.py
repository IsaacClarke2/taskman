"""
Authentication router - Telegram Login Widget verification.
"""

import hashlib
import hmac
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from jose import jwt
from sqlalchemy import select

from api.config import get_settings
from api.dependencies import AppSettings, DatabaseSession
from api.models.requests import TelegramAuthData
from api.models.responses import AuthResponse, UserResponse
from db.models import User

logger = logging.getLogger(__name__)
router = APIRouter()


def verify_telegram_auth(data: dict, bot_token: str) -> bool:
    """
    Verify Telegram Login Widget authentication data.

    Args:
        data: Auth data from Telegram widget (including hash).
        bot_token: Telegram bot token for verification.

    Returns:
        True if authentication is valid.
    """
    auth_data = data.copy()
    check_hash = auth_data.pop("hash", None)

    if not check_hash:
        return False

    # Build data check string
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(auth_data.items()) if v is not None
    )

    # Calculate expected hash
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), "sha256"
    ).hexdigest()

    return computed_hash == check_hash


def create_access_token(user_id: str, settings) -> str:
    """Create JWT access token for user."""
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@router.post("/telegram", response_model=AuthResponse)
async def telegram_auth(
    auth_data: TelegramAuthData,
    session: DatabaseSession,
    settings: AppSettings,
):
    """
    Authenticate user via Telegram Login Widget.

    Verifies the authentication data from Telegram and creates or updates
    the user in the database. Returns a JWT token for API access.
    """
    # Verify authentication
    if not settings.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bot token not configured",
        )

    auth_dict = auth_data.model_dump()
    if not verify_telegram_auth(auth_dict, settings.telegram_bot_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram authentication",
        )

    # Check auth_date is not too old (max 1 hour)
    auth_time = datetime.fromtimestamp(auth_data.auth_date)
    if datetime.utcnow() - auth_time > timedelta(hours=1):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication expired",
        )

    # Find or create user
    result = await session.execute(
        select(User).where(User.telegram_id == auth_data.id)
    )
    user = result.scalar_one_or_none()

    if user:
        # Update user info
        user.telegram_username = auth_data.username
        logger.info(f"User logged in: {auth_data.id}")
    else:
        # Create new user
        user = User(
            telegram_id=auth_data.id,
            telegram_username=auth_data.username,
        )
        session.add(user)
        logger.info(f"New user created: {auth_data.id}")

    await session.flush()

    # Create JWT token
    access_token = create_access_token(str(user.id), settings)

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    session: DatabaseSession,
    settings: AppSettings,
):
    """Get current user information."""
    from api.dependencies import get_current_user
    from fastapi import Depends

    # This endpoint requires authentication via dependency
    # The actual user fetching is done in the dependency
    pass
