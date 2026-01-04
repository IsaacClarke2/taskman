"""
Proactive token refresh manager.

Implements 5-minute buffer check before token expiration
and automatic persistence after refresh.
"""

import logging
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.utils.crypto import decrypt_credentials, encrypt_credentials
from db.models import Integration

logger = logging.getLogger(__name__)

# Refresh buffer (5 minutes before expiration)
TOKEN_REFRESH_BUFFER = 300


def is_token_expired(credentials: dict, buffer_seconds: int = TOKEN_REFRESH_BUFFER) -> bool:
    """
    Check if token is expired or will expire soon.

    Args:
        credentials: Token credentials dict
        buffer_seconds: Buffer time before expiration

    Returns:
        True if token needs refresh
    """
    expires_at = credentials.get("expires_at")

    if not expires_at:
        # No expiration info, assume valid
        return False

    # expires_at can be int (Unix timestamp) or float
    if isinstance(expires_at, (int, float)):
        return time.time() >= (expires_at - buffer_seconds)

    return False


def add_expiration_time(tokens: dict) -> dict:
    """
    Add expires_at timestamp to token response.

    Args:
        tokens: OAuth token response

    Returns:
        Tokens with expires_at added
    """
    if "expires_in" in tokens and "expires_at" not in tokens:
        tokens["expires_at"] = time.time() + tokens["expires_in"]

    return tokens


async def ensure_valid_token(
    session: AsyncSession,
    integration: Integration,
    connector_class,
) -> dict:
    """
    Ensure token is valid, refresh if needed.

    Args:
        session: Database session
        integration: Integration record
        connector_class: Connector class for refresh

    Returns:
        Valid credentials dict
    """
    credentials = decrypt_credentials(integration.credentials.get("encrypted", ""))

    if not is_token_expired(credentials):
        return credentials

    logger.info(f"Token expired for {integration.provider}, refreshing...")

    # Create connector and refresh
    connector = connector_class(credentials)
    new_credentials = await connector.refresh_token()

    # Add expiration time if not present
    new_credentials = add_expiration_time(new_credentials)

    # Save to database
    encrypted = encrypt_credentials(new_credentials)
    integration.credentials = {"encrypted": encrypted}
    await session.flush()

    logger.info(f"Token refreshed for {integration.provider}")
    return new_credentials


async def get_valid_connector(
    session: AsyncSession,
    user_id: int,
    provider: str,
    connector_class,
):
    """
    Get connector with valid (refreshed if needed) credentials.

    Args:
        session: Database session
        user_id: User ID
        provider: Integration provider
        connector_class: Connector class

    Returns:
        Connector instance with valid credentials
    """
    result = await session.execute(
        select(Integration).where(
            Integration.user_id == user_id,
            Integration.provider == provider,
            Integration.is_active == True,
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise IntegrationNotFoundError(f"No active {provider} integration found")

    credentials = await ensure_valid_token(session, integration, connector_class)
    return connector_class(credentials)


class IntegrationNotFoundError(Exception):
    """Raised when integration is not found."""
    pass


class TokenRefreshError(Exception):
    """Raised when token refresh fails."""
    pass
