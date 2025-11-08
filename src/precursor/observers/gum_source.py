# src/precursor/observers/gum_source.py
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional

from dotenv import load_dotenv
from gum import gum
from gum.observers import Calendar
from gum.observers import Screen

from precursor.context.events import ContextEvent
from precursor.context.utils import grab_screen_dspy_image
from precursor.config.loader import get_user_name, get_user_profile

logger = logging.getLogger(__name__)
load_dotenv()


class GumSource:
    """
    Real-time observer that listens to gum updates and converts them into
    `ContextEvent`s for the rest of the pipeline.

    Usage:
        async def handle(evt: ContextEvent):
            state_manager.process_event(evt)

        src = GumSource()
        await src.run(handle)
    """

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        poll_calendar_days: int = 3,
        max_batch_size: int = 15,
        capture_screenshot: bool = True,
    ) -> None:
        self.user_name = get_user_name()
        self.user_description = get_user_profile()
        self.model = model or os.getenv("GUM_MODEL") or "gpt-4o-mini-2024-07-18"
        self.poll_calendar_days = poll_calendar_days
        self.max_batch_size = max_batch_size
        self.capture_screenshot = capture_screenshot

    async def run(
        self,
        handler: Callable[[ContextEvent], Any] | Callable[[ContextEvent], Awaitable[Any]],
    ) -> None:
        """
        Open gum, register an update handler, and run forever.
        """
        cal = Calendar()
        screen = Screen(self.model)
        logger.info("Starting GumSource for user=%s, model=%s", self.user_name, self.model)

        async with gum(
            self.user_name,
            self.model,
            screen,
            cal,
            max_batch_size=self.max_batch_size,
        ) as gum_instance:

            async def _on_update(observer, update):
                # === Context ===
                context_update = update.content
                recent_propositions = await gum_instance.recent()
                calendar_events = cal.query_str(
                    start_delta=timedelta(days=0),
                    end_delta=timedelta(days=self.poll_calendar_days),
                )
                screenshot = grab_screen_dspy_image() if self.capture_screenshot else None

                # === Package event ===
                event = ContextEvent(
                    timestamp=datetime.now(timezone.utc),
                    context_update=context_update,
                    screenshot=screenshot,
                    user_name=self.user_name,
                    user_description=self.user_description,
                    recent_propositions=recent_propositions,  # same as user_details
                    calendar_events=calendar_events,
                    raw=update,
                )

                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result

            gum_instance.register_update_handler(_on_update)
            await asyncio.Future()


__all__ = ["GumSource"]