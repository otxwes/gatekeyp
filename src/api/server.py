# Copyright (c) 2026 Gatekeyp contributors

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.api.gateway import Gateway, RateLimiter
from src.core.content_manager import ContentAccessError, ContentManager, ContentValidationError
from src.core.event_lifecycle import EventLifecycleError, EventLifecycleManager
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler

# ------------------------------------------------------------------
# Request/Response Models
# ------------------------------------------------------------------


class AccessRequest(BaseModel):
    """Request to access content with a key."""

    key: str = Field(..., min_length=1, max_length=2048)
    content_id: str = Field(..., min_length=1, max_length=256)


class CreateEventRequest(BaseModel):
    """Request to create a new event."""

    title: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1, max_length=65536)
    organizer_id: str = Field(..., min_length=1, max_length=256)
    location_data: str | None = Field(default=None, max_length=1024)


class AddContentRequest(BaseModel):
    """Request to add a content block to an event."""

    master_key: str = Field(..., min_length=1, max_length=2048)
    event_id: str = Field(..., min_length=1, max_length=256)
    content_type: str = Field(..., min_length=1, max_length=64)
    payload: str = Field(..., min_length=1, max_length=65536)


class GenerateAccessKeyRequest(BaseModel):
    """Request to generate an attendee access key."""

    master_key: str = Field(..., min_length=1, max_length=2048)
    event_id: str = Field(..., min_length=1, max_length=256)
    days: int = Field(default=30, ge=1, le=365)
    owner_id: str | None = Field(default=None, max_length=256)


class RevokeAccessKeyRequest(BaseModel):
    """Request to revoke an attendee access key."""

    master_key: str = Field(..., min_length=1, max_length=2048)
    event_id: str = Field(..., min_length=1, max_length=256)
    access_key: str = Field(..., min_length=1, max_length=2048)


class DecommissionEventRequest(BaseModel):
    """Request to decommission an event."""

    master_key: str = Field(..., min_length=1, max_length=2048)
    event_id: str = Field(..., min_length=1, max_length=256)


class CreateBulletinRequest(BaseModel):
    """Request to create a bulletin on a communication board."""

    key: str = Field(..., min_length=1, max_length=2048)
    event_id: str = Field(..., min_length=1, max_length=256)
    title: str = Field(..., min_length=1, max_length=256)
    body: str = Field(..., min_length=1, max_length=65536)
    author_id: str = Field(..., min_length=1, max_length=256)


class AddCommentRequest(BaseModel):
    """Request to add a comment to a bulletin."""

    key: str = Field(..., min_length=1, max_length=2048)
    bulletin_id: str = Field(..., min_length=1, max_length=256)
    author_id: str = Field(..., min_length=1, max_length=256)
    body: str = Field(..., min_length=1, max_length=16384)


# ------------------------------------------------------------------
# Application Factory
# ------------------------------------------------------------------


def create_app(  # noqa: C901, PLR0915 - FastAPI app factory with many routes
    db: DatabaseHandler | None = None,
    key_manager: KeyManager | None = None,
    content_manager: ContentManager | None = None,
    lifecycle: EventLifecycleManager | None = None,
    gateway: Gateway | None = None,
) -> FastAPI:
    """
    Create the FastAPI application with all routes wired up.

    Args:
        db: Optional shared DatabaseHandler. If None, creates one.
        key_manager: Optional shared KeyManager. If None, creates one.
        content_manager: Optional shared ContentManager. If None, creates one.
        lifecycle: Optional shared EventLifecycleManager. If None, creates one.
        gateway: Optional shared Gateway. If None, creates one.

    Returns:
        Configured FastAPI application.
    """
    # Create shared services if not provided
    if db is None:
        db = DatabaseHandler()
    if key_manager is None:
        key_manager = KeyManager(db=db)
    if content_manager is None:
        content_manager = ContentManager(db=db, key_manager=key_manager)
    if lifecycle is None:
        lifecycle = EventLifecycleManager(
            db=db, key_manager=key_manager, content_manager=content_manager
        )
    if gateway is None:
        rate_limiter = RateLimiter()
        gateway = Gateway(db=db, key_manager=key_manager, rate_limiter=rate_limiter)

    app = FastAPI(
        title="Gatekeyp API",
        description="Privacy-preserving, federated event-organizing toolkit",
        version="0.1.0",
    )

    # CORS for the web UI
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO(@otxwes): Restrict in production (issue #42)  # noqa: FIX002
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health
    @app.get("/health")
    def health() -> dict:
        """Health check endpoint."""
        return {"status": "ok", "service": "gatekeyp"}

    # -- Access (Gateway) --
    @app.post("/api/access")
    def access_content(request: AccessRequest) -> dict:
        """Process an access request with a key."""
        return gateway.process_request(request.model_dump())

    # Event Lifecycle
    @app.post("/api/events")
    def create_event(request: CreateEventRequest) -> dict:
        """Create a new event with a master key."""
        try:
            return lifecycle.create_event(
                title=request.title,
                description=request.description,
                organizer_id=request.organizer_id,
                location_data=request.location_data,
            )
        except EventLifecycleError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @app.post("/api/events/{event_id}/content")
    def add_content(event_id: str, request: AddContentRequest) -> dict:
        """Add a content block to an event."""
        try:
            return lifecycle.add_content_block(
                master_key=request.master_key,
                event_id=event_id,
                content_type=request.content_type,
                payload=request.payload,
            )
        except EventLifecycleError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @app.get("/api/events/{event_id}")
    def get_event_details(event_id: str, master_key: str) -> dict:
        """Get full event details including all content blocks."""
        try:
            return lifecycle.get_event_details(master_key=master_key, event_id=event_id)
        except EventLifecycleError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @app.post("/api/events/{event_id}/access-keys")
    def generate_access_key(event_id: str, request: GenerateAccessKeyRequest) -> dict:
        """Generate an attendee access key for an event."""
        try:
            return lifecycle.generate_access_key(
                master_key=request.master_key,
                event_id=event_id,
                days=request.days,
                owner_id=request.owner_id,
            )
        except EventLifecycleError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @app.get("/api/events/{event_id}/access-keys")
    def list_access_keys(event_id: str, master_key: str) -> list[dict]:
        """List all access keys for an event."""
        try:
            return lifecycle.list_access_keys(master_key=master_key, event_id=event_id)
        except EventLifecycleError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @app.post("/api/events/{event_id}/access-keys/revoke")
    def revoke_access_key(event_id: str, request: RevokeAccessKeyRequest) -> dict:
        """Revoke an attendee access key."""
        try:
            revoked = lifecycle.revoke_access_key(
                master_key=request.master_key,
                event_id=event_id,
                access_key=request.access_key,
            )
        except EventLifecycleError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        else:
            return {"revoked": revoked}

    @app.post("/api/events/{event_id}/decommission")
    def decommission_event(event_id: str, request: DecommissionEventRequest) -> dict:
        """Decommission an event: revoke all keys."""
        try:
            return lifecycle.decommission_event(
                master_key=request.master_key,
                event_id=event_id,
            )
        except EventLifecycleError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    # -- Content (ContentManager) --
    @app.post("/api/events/{event_id}/media")
    async def upload_media(
        event_id: str,
        key: str,
        file: UploadFile,
    ) -> dict:
        """Upload a media asset (flyer, image, document) for an event."""
        data = await file.read()
        try:
            return content_manager.upload_media(
                input_key=key,
                event_id=event_id,
                filename=file.filename or "unnamed",
                mime_type=file.content_type or "application/octet-stream",
                data=data,
            )
        except (ContentValidationError, ContentAccessError) as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @app.get("/api/media/{asset_id}")
    def get_media(asset_id: str, key: str) -> dict:
        """Retrieve a media asset."""
        try:
            return content_manager.get_media(input_key=key, asset_id=asset_id)
        except (ContentValidationError, ContentAccessError) as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @app.post("/api/events/{event_id}/bulletins")
    def create_bulletin(event_id: str, request: CreateBulletinRequest) -> dict:
        """Create a bulletin on an event's communication board."""
        try:
            return content_manager.create_bulletin(
                input_key=request.key,
                event_id=event_id,
                title=request.title,
                body=request.body,
                author_id=request.author_id,
            )
        except (ContentValidationError, ContentAccessError) as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @app.get("/api/events/{event_id}/bulletins")
    def list_bulletins(event_id: str, key: str) -> list[dict]:
        """List all bulletins for an event."""
        try:
            return content_manager.list_bulletins(input_key=key, event_id=event_id)
        except (ContentValidationError, ContentAccessError) as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @app.post("/api/bulletins/{bulletin_id}/comments")
    def post_comment(bulletin_id: str, request: AddCommentRequest) -> dict:
        """Post a comment on a bulletin."""
        try:
            return content_manager.post_comment(
                input_key=request.key,
                bulletin_id=bulletin_id,
                author_id=request.author_id,
                body=request.body,
            )
        except (ContentValidationError, ContentAccessError) as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @app.get("/api/bulletins/{bulletin_id}/comments")
    def get_comments(bulletin_id: str, key: str) -> list[dict]:
        """Get all comments on a bulletin."""
        try:
            return content_manager.get_comments(input_key=key, bulletin_id=bulletin_id)
        except (ContentValidationError, ContentAccessError) as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    # Static Web UI
    static_dir = Path(__file__).parent.parent.parent / "web"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="web")

    return app


# ------------------------------------------------------------------
# Module-level app for uvicorn
# ------------------------------------------------------------------

app = create_app()


def main() -> None:
    """Run the server with uvicorn."""
    port = int(os.environ.get("GATEKEYP_PORT", "8000"))
    host = os.environ.get("GATEKEYP_HOST", "127.0.0.1")
    uvicorn.run("src.api.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
