"""LiveKit voice token endpoint.

Generates a short-lived access token that lets the browser participant
join a LiveKit room and hear the voice agent.

Room naming convention:  refundflow-<customer_id>
This means every unique customer gets their own isolated room, and the
voice agent's dispatch rule should target agent_name="refundflow-voice"
on any room matching the pattern `refundflow-*`.

Setup (add to backend/.env):
    LIVEKIT_URL=wss://your-project.livekit.cloud
    LIVEKIT_API_KEY=your_api_key
    LIVEKIT_API_SECRET=your_api_secret
"""

from __future__ import annotations

import os
import time

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

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
def get_voice_token(request: VoiceTokenRequest) -> VoiceTokenResponse:
    """Return a signed LiveKit JWT so the browser can join the voice room.

    The token grants the caller permission to publish (mic) and subscribe
    (agent audio) for the room dedicated to their customer_id.  It expires
    after 10 minutes — plenty for a typical support call.
    """
    api_key = os.getenv("LIVEKIT_API_KEY", "")
    api_secret = os.getenv("LIVEKIT_API_SECRET", "")
    livekit_url = os.getenv("LIVEKIT_URL", "")

    if not api_key or not api_secret or not livekit_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Voice agent is not configured. "
                "Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET in .env."
            ),
        )

    try:
        from livekit.api import AccessToken, VideoGrants  # type: ignore[import]
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="livekit-api package not installed. Run: pip install livekit-api",
        )

    room_name = f"refundflow-{request.customer_id.lower()}"
    identity = f"customer-{request.customer_id.lower()}"

    token = (
        AccessToken(api_key=api_key, api_secret=api_secret)
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
        .with_ttl(600)  # 10-minute token
        .to_jwt()
    )

    return VoiceTokenResponse(token=token, url=livekit_url, room_name=room_name)
