"""Single application-owned control loop.

Advances every authority on a fixed period regardless of how many clients read state.
Reads (GET routes, socket publication) never advance control; commands tick immediately
so protective shedding is prompt, and this loop handles time-based restoration.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, Iterable

log = logging.getLogger(__name__)

CONTROL_PERIOD_S = 0.25


class ControlLoop:
    def __init__(self, tickers: Iterable[Callable[[], object]], period_s: float = CONTROL_PERIOD_S,
                 publish: Callable[[], Awaitable[None]] | None = None, clock=time.monotonic):
        self.tickers = list(tickers)
        self.period_s = period_s
        self.publish = publish
        self.clock = clock
        self.task: asyncio.Task | None = None
        self.tick_count = 0
        self.missed_ticks = 0
        self.errors = 0
        self.last_error: str | None = None
        self.last_ok_monotonic: float | None = None
        self.last_ok_utc: str | None = None

    def tick_once(self) -> None:
        for tick in self.tickers:
            tick()
        self.tick_count += 1
        self.last_ok_monotonic = self.clock()
        self.last_ok_utc = datetime.now(timezone.utc).isoformat()

    async def run(self) -> None:
        next_at = self.clock()
        while True:
            try:
                self.tick_once()
            except Exception as exc:  # keep controlling; surface the failure in health
                self.errors += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                log.exception("control tick failed")
            if self.publish is not None:
                try:
                    await self.publish()
                except Exception as exc:
                    self.last_error = f"publish {type(exc).__name__}: {exc}"
            next_at += self.period_s
            now = self.clock()
            if now > next_at:
                # Overrun: skip the missed periods instead of replaying them back to back.
                skipped = int((now - next_at) // self.period_s) + 1
                self.missed_ticks += skipped
                next_at += skipped * self.period_s
            await asyncio.sleep(max(0.0, next_at - now))

    def start(self) -> None:
        if self.task is not None and not self.task.done():
            raise RuntimeError("control loop already running")
        self.task = asyncio.create_task(self.run(), name="control-loop")

    async def stop(self) -> None:
        if self.task is None:
            return
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        self.task = None

    def health(self) -> dict:
        age = None if self.last_ok_monotonic is None else round(self.clock() - self.last_ok_monotonic, 3)
        return {"running": self.task is not None and not self.task.done(), "period_s": self.period_s,
                "tick_count": self.tick_count, "missed_ticks": self.missed_ticks, "errors": self.errors,
                "last_error": self.last_error, "last_tick_age_s": age, "last_tick_at": self.last_ok_utc}
