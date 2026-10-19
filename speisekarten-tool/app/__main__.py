"""Start: `python -m app` (Optionen über MENU_TOOL_HOST / MENU_TOOL_PORT)."""

import logging
import os

import uvicorn

logging.basicConfig(level=logging.INFO)
uvicorn.run(
    "app.main:create_app",
    factory=True,
    host=os.environ.get("MENU_TOOL_HOST", "127.0.0.1"),
    port=int(os.environ.get("MENU_TOOL_PORT", "8000")),
)
