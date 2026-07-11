from __future__ import annotations
from typing import Awaitable, Callable, List

from app.modules.events.schemas import DomainEvent

EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventDispatcher:
    def __init__(self):
        self._handlers: List[EventHandler] = []

    def register(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    async def emit(self, event: DomainEvent) -> None:
        for handler in self._handlers:
            await handler(event)


dispatcher = EventDispatcher()
