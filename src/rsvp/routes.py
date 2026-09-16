# Copyright (c) 2026 gatekeyp contributors

"""HTTP routes for the RSVP funnel.

The attendee side is intentionally unauthenticated: anyone with the event id
can request an invite, subject to a per-client rate limit and an optional
shared passphrase. Every submission pre-mints its access key server-side; the
raw key is returned exactly once and stays grant-free until the organizer (or
the auto-approve dial) approves it. Organizer endpoints require the event's
organizer key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.rsvp.service import (
    MAX_AUTO_APPROVE,
    MAX_CONTACT_LENGTH,
    MAX_DISPLAY_NAME_LENGTH,
    RSVP_STATUS_PENDING,
    RsvpGoneError,
    RsvpNotFoundError,
    RsvpValidationError,
)

if TYPE_CHECKING:
    from src.rsvp.service import RsvpService

_RETRY_AFTER_SECONDS = "600"


class RsvpSubmissionRequest(BaseModel):
    """Request to RSVP to an event (unauthenticated, rate limited)."""

    display_name: str = Field(default="", max_length=MAX_DISPLAY_NAME_LENGTH)
    contact: str | None = Field(default=None, max_length=MAX_CONTACT_LENGTH)
    passphrase: str | None = Field(default=None, max_length=MAX_CONTACT_LENGTH)
    # Honeypot: humans never see this field (hidden in the form). Bots that
    # fill it get a canned acknowledgement and nothing is stored or minted.
    website: str | None = Field(default=None, max_length=256)


class RsvpDecisionRequest(BaseModel):
    """Organizer decision on a pending RSVP."""

    organizer_key: str = Field(
        ...,
        min_length=1,
        max_length=2048,
    )
    rsvp_id: str = Field(..., min_length=1, max_length=256)
    decision: str = Field(..., min_length=1, max_length=16)


class RsvpSettingsRequest(BaseModel):
    """Update the RSVP gate for an event (organizer-gated)."""

    organizer_key: str = Field(
        ...,
        min_length=1,
        max_length=2048,
    )
    passphrase: str | None = Field(default=None, max_length=MAX_CONTACT_LENGTH)
    auto_approve: int | None = Field(default=None, ge=0, le=MAX_AUTO_APPROVE)


def build_rsvp_router(  # noqa: C901 - many routes
    service: RsvpService,
) -> APIRouter:
    """Build the RSVP funnel router bound to the shared service."""
    router = APIRouter()

    @router.post("/api/events/{event_id}/rsvp", status_code=201)
    def submit_rsvp(event_id: str, body: RsvpSubmissionRequest, request: Request) -> dict:
        """Submit an RSVP and receive the pre-minted access card (shown once)."""
        if body.website:
            # Honeypot hit: acknowledge like a real submission, store nothing.
            return {
                "rsvp_id": None,
                "event_id": event_id,
                "status": RSVP_STATUS_PENDING,
                "message": "RSVP received; your access card will arrive once approved",
            }
        client_id = request.client.host if request.client else "unknown"
        if not service.rate_limiter.allow(client_id):
            raise HTTPException(
                status_code=429,
                detail="Too many RSVP attempts; try again later",
                headers={"Retry-After": _RETRY_AFTER_SECONDS},
            )
        try:
            return service.submit_rsvp(
                event_id,
                body.display_name or None,
                contact=body.contact,
                passphrase=body.passphrase,
            )
        except RsvpValidationError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        except RsvpNotFoundError as err:
            raise HTTPException(status_code=404, detail=str(err)) from err
        except RsvpGoneError as err:
            raise HTTPException(status_code=410, detail=str(err)) from err

    @router.get("/api/events/{event_id}/rsvp/view")
    def rsvp_public_view(event_id: str) -> JSONResponse:
        """Minimal public RSVP-page data: title, description, gate flags."""
        try:
            view = service.get_public_view(event_id)
        except RsvpNotFoundError as err:
            raise HTTPException(status_code=404, detail="Event not found") from err
        return JSONResponse(view, headers={"Cache-Control": "no-store"})

    @router.post("/api/events/{event_id}/rsvp/decide")
    def decide_rsvp(event_id: str, body: RsvpDecisionRequest) -> dict:
        """Approve or deny an RSVP (organizer-gated)."""
        try:
            return service.decide(body.organizer_key, event_id, body.rsvp_id, body.decision)
        except RsvpValidationError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        except RsvpNotFoundError as err:
            raise HTTPException(status_code=404, detail=str(err)) from err

    @router.get("/api/events/{event_id}/rsvp/settings")
    def get_rsvp_settings(event_id: str, key: str) -> dict:
        """Read the RSVP gate settings (organizer-gated)."""
        try:
            return service.get_rsvp_settings(key, event_id)
        except RsvpValidationError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @router.post("/api/events/{event_id}/rsvp/settings")
    def update_rsvp_settings(event_id: str, body: RsvpSettingsRequest) -> dict:
        """Set the RSVP gate: optional passphrase + auto-approve dial."""
        try:
            return service.update_rsvp_settings(
                body.organizer_key,
                event_id,
                passphrase=body.passphrase,
                auto_approve=body.auto_approve,
            )
        except RsvpValidationError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @router.get("/api/events/{event_id}/rsvp/list")
    def list_rsvps(event_id: str, key: str) -> list[dict]:
        """List RSVPs for the organizer tab (contacts decrypted server-side)."""
        try:
            return service.list_rsvps_for_event(key, event_id)
        except RsvpValidationError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    return router
