"""Shared MongoDB client options for CycleRM (Motor / PyMongo)."""

from __future__ import annotations

import certifi


def mongo_client_kwargs() -> dict:
    """TLS options that work reliably with MongoDB Atlas on Windows."""
    return {
        "tlsCAFile": certifi.where(),
        "serverSelectionTimeoutMS": 15_000,
        "connectTimeoutMS": 15_000,
    }
