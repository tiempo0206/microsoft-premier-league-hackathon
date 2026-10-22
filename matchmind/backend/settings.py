"""Small bounded server settings. Model credentials belong to the AI adapter."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    max_sessions: int = 8
    max_subscribers: int = 4
    queue_size: int = 64
    session_ttl: float = 1800
    idempotency_ttl: float = 1800
    max_idempotency_keys: int = 512
    tick_interval: float = 0.1
    snapshot_interval: float = 1
    max_request_bytes: int = 16384
    body_timeout: float = 10

    @classmethod
    def from_env(cls):
        names = {"max_sessions": ("MATCHMIND_MAX_REPLAY_SESSIONS", 1, 32),
                 "max_subscribers": ("MATCHMIND_MAX_SUBSCRIBERS_PER_REPLAY", 1, 8),
                 "queue_size": ("MATCHMIND_SSE_QUEUE_SIZE", 2, 256),
                 "session_ttl": ("MATCHMIND_SESSION_TTL_SEC", 30, 86400),
                 "max_request_bytes": ("MATCHMIND_MAX_REQUEST_BYTES", 256, 65536)}
        values = {}
        for field, (name, minimum, maximum) in names.items():
            raw = os.getenv(name)
            if raw is None:
                continue
            try:
                value = int(raw)
                if not minimum <= value <= maximum:
                    raise ValueError
            except ValueError:
                raise ValueError(f"{name} must be an integer between {minimum} and {maximum}") from None
            values[field] = value
        return cls(**values)
