# Copyright (c) 2026 gatekeyp contributors

"""HTTP routes for ephemeral ("lite") events.

The lite funnel is intentionally unauthenticated: organizers create events
without an account, everything except the flyer image stays behind keys, and
every event self-destructs after its TTL. Mounted in both server profiles.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse

from src.db.database_handler import DecryptionError
from src.ephemeral.service import LiteGoneError, LiteNotFoundError, LiteValidationError

if TYPE_CHECKING:
    from src.ephemeral.service import EphemeralService

_PAGE_STYLE = (
    "body{font-family:system-ui,sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem}"
    "h1{font-size:1.4rem}img{max-width:100%;height:auto;border-radius:8px}"
    ".notice{color:#555;font-size:.9rem}"
)

_RETRY_AFTER_SECONDS = "600"


def _render_page(title: str, head_html: str, body_html: str) -> str:
    """Wrap title, head snippets and body in the minimal page template."""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title>{head_html}"
        f"<style>{_PAGE_STYLE}</style></head><body>{body_html}</body></html>"
    )


def _render_ended_page(ended_at: str | None) -> str:
    """HTML for an expired or wiped event; crawlers are told to forget it."""
    body = (
        "<h1>Event ended</h1>"
        '<p class="notice">This event has ended and all of its data has been '
        "permanently deleted.</p>"
    )
    if ended_at:
        body += f'<p class="notice">Ended at: {html.escape(ended_at)}</p>'
    return _render_page("Event ended", '<meta name="robots" content="noindex">', body)


def _render_live_page(
    event_id: str, title: str, flyer_asset_id: str | None, expires_at: str | None, base_url: str
) -> str:
    """HTML plus Open Graph tags for a live ephemeral event."""
    og_image = ""
    flyer_tag = ""
    if flyer_asset_id:
        flyer_url = f"{base_url}/api/lite/events/{event_id}/flyer"
        og_image = f'<meta property="og:image" content="{html.escape(flyer_url)}">'
        flyer_tag = f'<img src="/api/lite/events/{event_id}/flyer" alt="{html.escape(title)}">'
    expires = html.escape(expires_at) if expires_at else "soon"
    body = (
        f"<h1>{html.escape(title)}</h1>"
        f"{flyer_tag}"
        '<p class="notice">This page is temporary. All event data is '
        f"automatically wiped after {expires}.</p>"
    )
    head = (
        '<meta property="og:type" content="website">'
        f'<meta property="og:title" content="{html.escape(title)}">'
        f"{og_image}"
        '<meta name="robots" content="noindex, noarchive">'
    )
    return _render_page(title, head, body)


def build_ephemeral_router(service: EphemeralService) -> APIRouter:  # noqa: C901, PLR0915 - many routes
    """Build the ephemeral events router bound to the shared service."""
    router = APIRouter()

    @router.post("/api/lite/events", status_code=201)
    async def create_lite_event(
        request: Request,
        title: Annotated[str, Form()],
        description: Annotated[str, Form()] = "",
        when: Annotated[str, Form()] = "",
        where: Annotated[str, Form()] = "",
        ttl_hours: Annotated[int, Form()] = 48,
        flyer: Annotated[UploadFile | None, File()] = None,
    ) -> dict:
        """
        Create an ephemeral lite event (organizer funnel, no login).

        Returns the event id, the master key (shown exactly once) and ready
        to share organizer/public URLs. Rate limited per client IP.
        """
        client_id = request.client.host if request.client else "unknown"
        if not service.rate_limiter.allow(client_id):
            raise HTTPException(
                status_code=429,
                detail="Too many lite events created; try again later",
                headers={"Retry-After": _RETRY_AFTER_SECONDS},
            )
        flyer_payload = None
        if flyer is not None and flyer.filename:
            flyer_payload = {
                "filename": flyer.filename,
                "mime_type": flyer.content_type or "application/octet-stream",
                "data": await flyer.read(),
            }
        try:
            result = service.create_lite_event(
                title,
                description=description or None,
                when=when or None,
                where=where or None,
                flyer=flyer_payload,
                ttl_hours=ttl_hours,
            )
        except LiteValidationError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

        base_url = str(request.base_url).rstrip("/")
        result["organizer_url"] = (
            f"{base_url}/#/organizer/{result['event_id']}?k={result['master_key']}"
        )
        result["public_url"] = f"{base_url}/i/{result['event_id']}"
        return result

    @router.get("/api/lite/events/{event_id}/flyer")
    def get_lite_flyer(event_id: str) -> Response:
        """Serve the public flyer image (no key; this is the event poster)."""
        try:
            view = service.get_public_view(event_id)
        except LiteNotFoundError as err:
            raise HTTPException(status_code=404, detail="Event not found") from err
        if view["status"] in ("ended", "expired"):
            raise HTTPException(status_code=410, detail="This event has ended")
        asset_id = view.get("flyer_asset_id")
        if asset_id is None:
            raise HTTPException(status_code=404, detail="No flyer for this event")
        try:
            asset = service.db.get_media_asset(asset_id)
        except DecryptionError as err:
            message = "Flyer could not be decrypted"
            raise HTTPException(status_code=500, detail=message) from err
        if asset is None:
            raise HTTPException(status_code=404, detail="Flyer not found")
        filename = quote(asset["filename"])
        return Response(
            content=asset["data"],
            media_type=asset["mime_type"],
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/api/lite/events/{event_id}")
    def get_lite_event(event_id: str, key: str) -> dict:
        """Keyed attendee view: title, description, when/where for key holders."""
        try:
            return service.get_keyed_view(key=key, event_id=event_id)
        except LiteNotFoundError as err:
            raise HTTPException(status_code=404, detail="Event not found") from err
        except LiteGoneError as err:
            raise HTTPException(status_code=410, detail=str(err)) from err
        except LiteValidationError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @router.get("/i/{event_id}")
    def lite_og_page(event_id: str, request: Request) -> HTMLResponse:
        """Public landing page with Open Graph tags (crawler + human friendly)."""
        try:
            view = service.get_public_view(event_id)
        except LiteNotFoundError as err:
            raise HTTPException(status_code=404, detail="Event not found") from err
        if view["status"] in ("ended", "expired"):
            page = _render_ended_page(view.get("ended_at"))
            return HTMLResponse(page, headers={"Cache-Control": "no-store"})
        event = view["event"]
        page = _render_live_page(
            event_id=event_id,
            title=event["title"],
            flyer_asset_id=view.get("flyer_asset_id"),
            expires_at=event.get("expires_at"),
            base_url=str(request.base_url).rstrip("/"),
        )
        return HTMLResponse(page, headers={"Cache-Control": "no-store"})

    return router
