from __future__ import annotations

from __future__ import annotations

from app.api import create_api
from app.config import get_settings

# Allows running `uvicorn app.main:app` directly.
app = create_api(get_settings())
