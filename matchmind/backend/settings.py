"""Small bounded server settings. Model credentials belong to the AI adapter."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    data_directory: str = "data/extra/validated-demo"
    serve_frontend: bool = False
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
    analysis_concurrency: int = 1
    analysis_queue_size: int = 8
    analysis_limit_per_hour: int = 30
    analysis_timeout: float = 12

    @classmethod
    def from_env(cls):
        names = {"max_sessions": ("MATCHMIND_MAX_REPLAY_SESSIONS", 1, 32),
                 "max_subscribers": ("MATCHMIND_MAX_SUBSCRIBERS_PER_REPLAY", 1, 8),
                 "queue_size": ("MATCHMIND_SSE_QUEUE_SIZE", 2, 256),
                 "session_ttl": ("MATCHMIND_SESSION_TTL_SEC", 30, 86400),
                 "max_request_bytes": ("MATCHMIND_MAX_REQUEST_BYTES", 256, 65536),
                 "analysis_concurrency": ("MATCHMIND_MAX_CONCURRENT_ANALYSES", 1, 4),
                 "analysis_queue_size": ("MATCHMIND_ANALYSIS_QUEUE_SIZE", 1, 32),
                 "analysis_limit_per_hour": ("MATCHMIND_ANALYSIS_LIMIT_PER_HOUR", 1, 1000),
                 "analysis_timeout": ("MATCHMIND_MODEL_TIMEOUT_SEC", 1, 60)}
        values = {}
        raw_directory = os.getenv("MATCHMIND_DATA_DIR")
        if raw_directory is not None:
            if not raw_directory.strip() or "\x00" in raw_directory:
                raise ValueError("MATCHMIND_DATA_DIR must name a dataset directory")
            values["data_directory"] = raw_directory
        raw_frontend = os.getenv("MATCHMIND_SERVE_FRONTEND", "0")
        if raw_frontend not in ("0", "1"):
            raise ValueError("MATCHMIND_SERVE_FRONTEND must be 0 or 1")
        values["serve_frontend"] = raw_frontend == "1"
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


def port_from_env():
    try:
        port = int(os.getenv("PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError
        return port
    except ValueError:
        raise ValueError("PORT must be an integer between 1 and 65535") from None
