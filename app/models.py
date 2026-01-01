from __future__ import annotations

# Re-export core models so the admin panel and Alembic share the same metadata.
from models import (  # noqa: F401
    ActionLog,
    AdminAction,
    Base,
    UaLocation,
    Like,
    Match,
    Message,
    Photo,
    Complaint,
    User,
)

__all__ = [
    "ActionLog",
    "AdminAction",
    "Base",
    "Complaint",
    "UaLocation",
    "Like",
    "Match",
    "Message",
    "Photo",
    "User",
]
