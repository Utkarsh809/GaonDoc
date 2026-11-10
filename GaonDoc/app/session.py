import secrets
import time
from dataclasses import dataclass, field
from typing import Optional

from .pipeline.state import CaseState

MAX_TURNS = 300


@dataclass
class Session:
    id: str
    patient_language: str
    doctor_language: str
    created: float
    touched: float
    state: CaseState = field(default_factory=CaseState)
    turns: list = field(default_factory=list)
    seen_flags: set = field(default_factory=set)
    prescription: Optional[dict] = None

    def add_turn(self, speaker, transcript, translation):
        if len(self.turns) >= MAX_TURNS:
            raise OverflowError("turn limit reached")
        self.turns.append({"n": len(self.turns) + 1, "speaker": speaker, "transcript": transcript, "translation": translation})
        return len(self.turns)


class SessionStore:
    def __init__(self, ttl_seconds, capacity=1000):
        self.ttl = ttl_seconds
        self.capacity = capacity
        self._items = {}

    def _purge(self):
        now = time.time()
        for sid in [k for k, v in self._items.items() if now - v.touched > self.ttl]:
            del self._items[sid]

    def create(self, patient_language, doctor_language):
        self._purge()
        if len(self._items) >= self.capacity:
            raise OverflowError("too many active sessions")
        now = time.time()
        session = Session(secrets.token_urlsafe(16), patient_language, doctor_language, now, now)
        self._items[session.id] = session
        return session

    def get(self, sid):
        self._purge()
        session = self._items[sid]
        session.touched = time.time()
        return session

    def delete(self, sid):
        self._items.pop(sid, None)
