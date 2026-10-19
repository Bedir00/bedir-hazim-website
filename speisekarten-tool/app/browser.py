"""Gemeinsamer Headless-Chromium für URL-Screenshots und PDF-Export."""

import asyncio

from playwright.async_api import Browser, Playwright, async_playwright


class BrowserManager:
    def __init__(self, executable_path: str | None = None):
        self._executable_path = executable_path
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> Browser:
        async with self._lock:
            if self._browser is None or not self._browser.is_connected():
                if self._playwright is None:
                    self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    executable_path=self._executable_path
                )
            return self._browser

    @property
    def playwright(self) -> Playwright | None:
        return self._playwright

    async def close(self) -> None:
        async with self._lock:
            if self._browser is not None:
                await self._browser.close()
                self._browser = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None
