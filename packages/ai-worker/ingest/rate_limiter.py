import asyncio
import time


class RateLimiter:
    def __init__(self, delay_seconds: float = 30.0):
        self.delay_seconds = delay_seconds
        self._last_request_at: float | None = None

    async def wait(self) -> None:
        if self._last_request_at is None:
            self._last_request_at = time.monotonic()
            return

        elapsed = time.monotonic() - self._last_request_at
        remaining = self.delay_seconds - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
        self._last_request_at = time.monotonic()
