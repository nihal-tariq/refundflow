"""LiveKit voice token endpoint.

Generates a short-lived access token that lets the browser participant
join a LiveKit room and hear the voice agent.

Room naming convention:  refundflow-<customer_id>
This means every unique customer gets their own isolated room, and the
voice agent's dispatch rule should target agent_name="refundflow-voice"
on any room matching the pattern `refundflow-*`.

Credentials are sourced from Settings (loaded from .env) so they respect
the same configuration system as every other backend setting.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.config.settings import Settings

router = APIRouter(tags=["voice"])


class VoiceTokenRequest(BaseModel):
    customer_id: str


class VoiceTokenResponse(BaseModel):
    token: str
    url: str
    room_name: str


@router.post(
    "/voice/token",
    response_model=VoiceTokenResponse,
    summary="Generate a LiveKit access token for the voice agent room",
)
def get_voice_token(
    request: VoiceTokenRequest,
    settings: Settings = Depends(get_settings),
) -> VoiceTokenResponse:
    """Return a signed LiveKit JWT so the browser can join the voice room.

    The token grants the caller permission to publish (mic) and subscribe
    (agent audio) for the room dedicated to their customer_id.  It expires
    after 10 minutes — plenty for a typical support call.
    """
    if not settings.livekit_url or not settings.livekit_api_key or not settings.livekit_api_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Voice agent is not configured. "
                "Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET in .env."
            ),
        )

    try:
        from livekit.api import (  # type: ignore[import]
            AccessToken,
            RoomAgentDispatch,
            RoomConfiguration,
            VideoGrants,
        )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="livekit-api package not installed. Run: pip install livekit-api",
        )

    room_name = f"refundflow-{request.customer_id.lower()}"
    identity = f"customer-{request.customer_id.lower()}"

    # The voice worker registers with an explicit agent_name, so it uses
    # *explicit* dispatch — it never auto-joins rooms. Embedding the dispatch in
    # the token tells LiveKit to spin the agent into this room the moment the
    # browser connects; without this the customer joins an empty (silent) room.
    token = (
        AccessToken(api_key=settings.livekit_api_key, api_secret=settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(request.customer_id)
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .with_room_config(
            RoomConfiguration(
                agents=[RoomAgentDispatch(agent_name="refundflow-voice")],
            )
        )
        .with_ttl(datetime.timedelta(minutes=10))  # 10-minute token
        .to_jwt()
    )
    return VoiceTokenResponse(token=token, url=settings.livekit_url, room_name=room_name)