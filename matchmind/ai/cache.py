"""Bounded cache for model responses.

Design decision worth stating: this caches the **model response**, not the finished card.

Caching the whole AnalysisResult would mean rewriting `task_id`, `replay_id`, `run_id` and every
trace entry on a hit, and a trace that names another request's task id is a lie. Caching only the
HTTP response keeps the pipeline honest: the code gates run again, the traces are this request's
own, and the identity fields are never touched. The cost saving is the same, because the model
call is the entire cost.

The key includes the prompt version, the model, the thinking setting and the exact prompt text, so
a prompt change cannot be served from a stale entry. It deliberately excludes `task_id`,
`replay_id` and `run_id`: those identify a request, not its content.

    from ai.cache import ResponseCache
    cache = ResponseCache()
    cache.get(key) -> dict | None
"""
import hashlib
import json
import os
from collections import OrderedDict

DEFAULT_MAX_ENTRIES = 256
ENV_FLAG = "MATCHMIND_CACHE"


def enabled():
    """On by default: the saving is free and the honesty cost is zero because only the HTTP
    response is reused. Set MATCHMIND_CACHE=0 to disable."""
    return os.getenv(ENV_FLAG, "1").strip() not in ("0", "false", "no", "")


def key_for(*, model, thinking, system, user, max_tokens, tools=False):
    """Stable key over everything that changes what the model would say."""
    payload = json.dumps({"model": model, "thinking": thinking, "system": system,
                          "user": user, "max_tokens": max_tokens, "tools": bool(tools)},
                         ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResponseCache:
    """OrderedDict LRU. Not thread safe; this pipeline is single-threaded asyncio."""

    def __init__(self, max_entries=DEFAULT_MAX_ENTRIES):
        self.max_entries = max(1, int(max_entries))
        self._store = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        value = self._store.get(key)
        if value is None:
            self.misses += 1
            return None
        self._store.move_to_end(key)
        self.hits += 1
        return value

    def put(self, key, value):
        self._store[key] = value
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def clear(self):
        self._store.clear()

    def __len__(self):
        return len(self._store)

    def stats(self):
        total = self.hits + self.misses
        return {"entries": len(self._store), "max_entries": self.max_entries,
                "hits": self.hits, "misses": self.misses,
                "hit_rate": round(self.hits / total, 3) if total else None}


# One process-wide cache: the replay server is a single process by contract, and a per-request
# cache would never hit.
CACHE = ResponseCache(int(os.getenv("MATCHMIND_CACHE_ENTRIES", DEFAULT_MAX_ENTRIES)))
