"""
Integrations router - OAuth flows and integration management.
"""

import logging
import secrets
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from api.config import get_settings
from api.dependencies import AppSettings, CurrentUser, DatabaseSession
from api.models.requests import AppleCalendarConnectRequest, IntegrationConnectRequest
from api.models.responses import IntegrationResponse, IntegrationStatusResponse, OAuthURLResponse
from api.utils.crypto import encrypt_credentials
from db.models import Integration

logger = logging.getLogger(__name__)
router = APIRouter()

# OAuth state storage (in production, use Redis)
_oauth_states: dict[str, str] = {}


# ============= OAuth URL Generation =============


@router.get("/google/auth", response_model=OAuthURLResponse)
async def get_google_auth_url(settings: AppSettings):
    """Get Google OAuth authorization URL."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured",
        )

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = "google"

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    return OAuthURLResponse(authorization_url=url, state=state)


@router.get("/outlook/auth", response_model=OAuthURLResponse)
async def get_outlook_auth_url(settings: AppSettings):
    """Get Microsoft OAuth authorization URL."""
    if not settings.microsoft_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Microsoft OAuth not configured",
        )

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = "outlook"

    params = {
        "client_id": settings.microsoft_client_id,
        "response_type": "code",
        "redirect_uri": settings.microsoft_redirect_uri,
        "response_mode": "query",
        "scope": "offline_access Calendars.ReadWrite User.Read",
        "state": state,
    }
    url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{urlencode(params)}"

    return OAuthURLResponse(authorization_url=url, state=state)


@router.get("/notion/auth", response_model=OAuthURLResponse)
async def get_notion_auth_url(settings: AppSettings):
    """Get Notion OAuth authorization URL."""
    if not settings.notion_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Notion OAuth not configured",
        )

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = "notion"

    params = {
        "client_id": settings.notion_client_id,
        "response_type": "code",
        "owner": "user",
        "redirect_uri": settings.notion_redirect_uri,
        "state": state,
    }
    url = f"https://api.notion.com/v1/oauth/authorize?{urlencode(params)}"

    return OAuthURLResponse(authorization_url=url, state=state)


@router.get("/zoom/auth", response_model=OAuthURLResponse)
async def get_zoom_auth_url(settings: AppSettings):
    """Get Zoom OAuth authorization URL."""
    if not settings.zoom_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Zoom OAuth not configured",
        )

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = "zoom"

    params = {
        "client_id": settings.zoom_client_id,
        "response_type": "code",
        "redirect_uri": settings.zoom_redirect_uri,
        "state": state,
    }
    url = f"https://zoom.us/oauth/authorize?{urlencode(params)}"

    return OAuthURLResponse(authorization_url=url, state=state)


# ============= OAuth Callbacks =============


@router.post("/google/callback", response_model=IntegrationResponse)
async def google_oauth_callback(
    request: IntegrationConnectRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
    settings: AppSettings,
):
    """Handle Google OAuth callback and store tokens."""
    import httpx

    # Verify state
    if request.state and _oauth_states.get(request.state) != "google":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": request.code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.google_redirect_uri,
            },
        )

        if response.status_code != 200:
            logger.error(f"Google token exchange failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code",
            )

        tokens = response.json()

    # Store integration
    integration = await _create_or_update_integration(
        session=session,
        user_id=current_user.id,
        provider="google_calendar",
        credentials=tokens,
    )

    # Clean up state
    if request.state:
        _oauth_states.pop(request.state, None)

    return IntegrationResponse.model_validate(integration)


@router.post("/outlook/callback", response_model=IntegrationResponse)
async def outlook_oauth_callback(
    request: IntegrationConnectRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
    settings: AppSettings,
):
    """Handle Microsoft OAuth callback and store tokens."""
    import httpx

    # Verify state
    if request.state and _oauth_states.get(request.state) != "outlook":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "code": request.code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.microsoft_redirect_uri,
                "scope": "offline_access Calendars.ReadWrite User.Read",
            },
        )

        if response.status_code != 200:
            logger.error(f"Microsoft token exchange failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code",
            )

        tokens = response.json()

    # Store integration
    integration = await _create_or_update_integration(
        session=session,
        user_id=current_user.id,
        provider="outlook",
        credentials=tokens,
    )

    if request.state:
        _oauth_states.pop(request.state, None)

    return IntegrationResponse.model_validate(integration)


@router.post("/notion/callback", response_model=IntegrationResponse)
async def notion_oauth_callback(
    request: IntegrationConnectRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
    settings: AppSettings,
):
    """Handle Notion OAuth callback and store tokens."""
    import base64

    import httpx

    # Verify state
    if request.state and _oauth_states.get(request.state) != "notion":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    # Notion uses Basic auth for token exchange
    credentials = base64.b64encode(
        f"{settings.notion_client_id}:{settings.notion_client_secret}".encode()
    ).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.notion.com/v1/oauth/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            json={
                "grant_type": "authorization_code",
                "code": request.code,
                "redirect_uri": settings.notion_redirect_uri,
            },
        )

        if response.status_code != 200:
            logger.error(f"Notion token exchange failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code",
            )

        tokens = response.json()

    # Store integration
    integration = await _create_or_update_integration(
        session=session,
        user_id=current_user.id,
        provider="notion",
        credentials=tokens,
    )

    if request.state:
        _oauth_states.pop(request.state, None)

    return IntegrationResponse.model_validate(integration)


@router.post("/apple-calendar", response_model=IntegrationResponse)
async def connect_apple_calendar(
    request: AppleCalendarConnectRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
):
    """Connect Apple Calendar via CalDAV with app-specific password."""
    import caldav

    # Test CalDAV connection
    try:
        client = caldav.DAVClient(
            url="https://caldav.icloud.com",
            username=request.email,
            password=request.app_password,
        )
        principal = client.principal()
        calendars = principal.calendars()
        logger.info(f"Connected to Apple Calendar: {len(calendars)} calendars found")
    except Exception as e:
        logger.error(f"Apple Calendar connection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to connect to Apple Calendar. Check email and app-specific password.",
        )

    # Store integration
    credentials = {
        "email": request.email,
        "app_password": request.app_password,
    }

    integration = await _create_or_update_integration(
        session=session,
        user_id=current_user.id,
        provider="apple_calendar",
        credentials=credentials,
    )

    return IntegrationResponse.model_validate(integration)


@router.post("/zoom/callback", response_model=IntegrationResponse)
async def zoom_oauth_callback(
    request: IntegrationConnectRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
    settings: AppSettings,
):
    """Handle Zoom OAuth callback and store tokens."""
    from api.connectors.zoom import ZoomConnector

    # Verify state
    if request.state and _oauth_states.get(request.state) != "zoom":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    # Exchange code for tokens
    try:
        tokens = await ZoomConnector.exchange_code(
            code=request.code,
            client_id=settings.zoom_client_id,
            client_secret=settings.zoom_client_secret,
            redirect_uri=settings.zoom_redirect_uri,
        )
    except Exception as e:
        logger.error(f"Zoom token exchange failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange authorization code",
        )

    # Store integration
    integration = await _create_or_update_integration(
        session=session,
        user_id=current_user.id,
        provider="zoom",
        credentials=tokens,
    )

    if request.state:
        _oauth_states.pop(request.state, None)

    return IntegrationResponse.model_validate(integration)


@router.post("/yandex/connect", response_model=IntegrationResponse)
async def connect_yandex_calendar(
    request: AppleCalendarConnectRequest,  # Same structure: email + app_password
    current_user: CurrentUser,
    session: DatabaseSession,
):
    """Connect Yandex Calendar via CalDAV with app-specific password."""
    import caldav

    # Test CalDAV connection
    try:
        client = caldav.DAVClient(
            url="https://caldav.yandex.ru",
            username=request.email,
            password=request.app_password,
        )
        principal = client.principal()
        calendars = principal.calendars()
        logger.info(f"Connected to Yandex Calendar: {len(calendars)} calendars found")
    except Exception as e:
        logger.error(f"Yandex Calendar connection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to connect to Yandex Calendar. Check login and app-specific password.",
        )

    # Store integration
    credentials = {
        "username": request.email,
        "app_password": request.app_password,
    }

    integration = await _create_or_update_integration(
        session=session,
        user_id=current_user.id,
        provider="yandex_calendar",
        credentials=credentials,
    )

    return IntegrationResponse.model_validate(integration)


# ============= Integration Management =============


@router.get("/status", response_model=IntegrationStatusResponse)
async def get_integration_status(
    current_user: CurrentUser,
    session: DatabaseSession,
):
    """Get status of all integrations for current user."""
    result = await session.execute(
        select(Integration).where(Integration.user_id == current_user.id)
    )
    integrations = result.scalars().all()

    status = IntegrationStatusResponse()
    for integration in integrations:
        response = IntegrationResponse.model_validate(integration)
        if integration.provider == "google_calendar":
            status.google_calendar = response
        elif integration.provider == "outlook":
            status.outlook = response
        elif integration.provider == "apple_calendar":
            status.apple_calendar = response
        elif integration.provider == "yandex_calendar":
            status.yandex_calendar = response
        elif integration.provider == "notion":
            status.notion = response
        elif integration.provider == "zoom":
            status.zoom = response

    return status


@router.delete("/{provider}")
async def disconnect_integration(
    provider: str,
    current_user: CurrentUser,
    session: DatabaseSession,
):
    """Disconnect an integration."""
    result = await session.execute(
        select(Integration).where(
            Integration.user_id == current_user.id,
            Integration.provider == provider,
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )

    await session.delete(integration)
    return {"status": "disconnected", "provider": provider}


# ============= Helper Functions =============


async def _create_or_update_integration(
    session,
    user_id,
    provider: str,
    credentials: dict,
) -> Integration:
    """Create or update an integration."""
    result = await session.execute(
        select(Integration).where(
            Integration.user_id == user_id,
            Integration.provider == provider,
        )
    )
    integration = result.scalar_one_or_none()

    encrypted_credentials = encrypt_credentials(credentials)

    if integration:
        integration.credentials = {"encrypted": encrypted_credentials}
        integration.is_active = True
        logger.info(f"Updated integration: {provider}")
    else:
        integration = Integration(
            user_id=user_id,
            provider=provider,
            credentials={"encrypted": encrypted_credentials},
            is_active=True,
        )
        session.add(integration)
        logger.info(f"Created integration: {provider}")

    await session.flush()
    return integration
