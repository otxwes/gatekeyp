# Copyright (c) 2026 gatekeyp contributors

"""Ephemeral ("lite") events: short-lived flyer events with automatic wiping."""

from src.ephemeral.routes import build_ephemeral_router
from src.ephemeral.service import (
    DEFAULT_TTL_HOURS,
    MAX_TTL_HOURS,
    MIN_TTL_HOURS,
    EphemeralService,
    LiteGoneError,
    LiteNotFoundError,
    LiteRateLimiter,
    LiteRateLimitError,
    LiteValidationError,
)

__all__ = [
    "DEFAULT_TTL_HOURS",
    "MAX_TTL_HOURS",
    "MIN_TTL_HOURS",
    "EphemeralService",
    "LiteGoneError",
    "LiteNotFoundError",
    "LiteRateLimitError",
    "LiteRateLimiter",
    "LiteValidationError",
    "build_ephemeral_router",
]
