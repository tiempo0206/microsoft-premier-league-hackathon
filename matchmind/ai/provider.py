"""Chat Completions transport for Role C.

Provider-neutral: any OpenAI-compatible endpoint works. DeepSeek is verified for
JSON Output and Tool Calls, so the same code path serves it and Qwen.

No credential is ever logged, echoed, embedded in an exception message or written to
disk. Errors are re-raised as bounded, non-retryable-forever failures.
"""
import asyncio
import json
import time

import httpx


class ProviderError(Exception):
    """Bounded, sanitised model failure. Never carries the API key or the raw body."""

    def __init__(self, kind, detail, *, status=None, retryable=False):
        super().__init__(kind + ": " + detail)
        self.kind = kind
        self.detail = detail
        self.status = status
        self.retryable = retryable


class ProviderTimeout(ProviderError):
    def __init__(self, detail="model deadline exceeded"):
        super().__init__("TIMEOUT", detail, retryable=True)


def _default_cache():
    """The process-wide response cache, or None when it is switched off."""
    from . import cache as cache_module
    return cache_module.CACHE if cache_module.enabled() else None


class ChatCompletionsProvider:
    def __init__(self, config, *, transport=None, clock=time.monotonic, cache=None,
                 use_cache=True):
        self.config = config
        self.transport = transport
        self.clock = clock
        self.calls = 0
        self.last_usage = None
        self.last_served_model = None
        # A cache only helps if it survives between requests, so the default is the
        # process-wide one. `use_cache=False` bypasses it entirely, which is what tests that
        # count HTTP calls need.
        self.cache = cache if cache is not None else (_default_cache() if use_cache else None)
        self.cache_hits = 0
        # Token accounting for this provider instance, which is one analysis.
        from .usage import UsageLedger
        self.usage = UsageLedger()

    # -- request body -------------------------------------------------------
    def _body(self, messages, *, max_tokens, tools=None):
        body = {
            "model": self.config.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "stream": False,
            "max_tokens": max_tokens,
        }
        # DeepSeek enables thinking by default at effort "high"; that does not fit the
        # frozen 12s analysis deadline. The documented OpenAI-format toggle is a
        # top-level "thinking" object, so we set it explicitly on every call.
        thinking = self.config.thinking
        if thinking == "disabled":
            body["thinking"] = {"type": "disabled"}
        else:
            body["thinking"] = {"type": "enabled"}
            body["reasoning_effort"] = thinking
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        return body

    def _client(self, timeout):
        kwargs = {"timeout": httpx.Timeout(timeout)}
        if self.transport is not None:
            kwargs["transport"] = self.transport
        return httpx.AsyncClient(**kwargs)

    async def _post(self, body, remaining):
        if remaining <= 0:
            raise ProviderTimeout()
        url = self.config.base_url + "/chat/completions"
        headers = {"Authorization": "Bearer " + self.config.api_key,
                   "Content-Type": "application/json"}
        try:
            async with self._client(remaining) as client:
                response = await asyncio.wait_for(
                    client.post(url, headers=headers, json=body), timeout=remaining)
        except (asyncio.TimeoutError, httpx.TimeoutException):
            raise ProviderTimeout() from None
        except httpx.HTTPError as error:
            raise ProviderError("NETWORK", type(error).__name__) from None
        self.calls += 1
        if response.status_code != 200:
            hint = {401: "key or region", 403: "model permission", 404: "base URL or model name",
                    429: "quota or rate limit", 400: "request parameters"}.get(response.status_code, "upstream")
            raise ProviderError("HTTP_" + str(response.status_code), hint,
                                status=response.status_code, retryable=response.status_code in (429, 500, 502, 503, 504))
        try:
            payload = response.json()
            message = payload["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("BAD_ENVELOPE", "response was not a chat completion") from None
        self.last_usage = payload.get("usage")
        self.last_served_model = payload.get("model") or self.config.model
        self.usage.add(self.last_usage, self.last_served_model)
        return message

    @staticmethod
    def _json_content(message):
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("EMPTY", "model returned no content")
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        try:
            value = json.loads(text)
        except ValueError:
            raise ProviderError("NOT_JSON", "model returned non-JSON content") from None
        if not isinstance(value, dict):
            raise ProviderError("NOT_OBJECT", "model returned a non-object JSON value")
        return value

    async def complete_json(self, *, system, user, deadline, max_tokens=900):
        """One structured completion. Raises ProviderError/ProviderTimeout only."""
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise ProviderTimeout()
        if self.cache is not None:
            from .cache import key_for
            key = key_for(model=self.config.model, thinking=self.config.thinking,
                          system=system, user=user, max_tokens=max_tokens, tools=False)
            cached = self.cache.get(key)
            if cached is not None:
                self.cache_hits += 1
                self.usage.add(None, cached=True)
                return dict(cached)
        body = self._body([{"role": "system", "content": system},
                           {"role": "user", "content": user}], max_tokens=max_tokens)
        message = await self._post(body, remaining)
        value = self._json_content(message)
        if self.cache is not None:
            self.cache.put(key, dict(value))
        return value

    async def complete_with_tools(self, *, system, user, deadline, toolbox,
                                  tool_schemas, max_tool_calls=3, max_tokens=900):
        """Bounded tool loop. Thinking is disabled on this path so that DeepSeek does
        not require reasoning_content to be echoed back, which is only mandatory when
        tools are combined with thinking mode.

        Cached as a whole: the toolbox is scoped to the same request, so the same prompt yields
        the same tool results and therefore the same final JSON.
        """
        cached_key = None
        if self.cache is not None:
            from .cache import key_for
            cached_key = key_for(model=self.config.model, thinking=self.config.thinking,
                                 system=system, user=user, max_tokens=max_tokens, tools=True)
            cached = self.cache.get(cached_key)
            if cached is not None:
                self.cache_hits += 1
                self.usage.add(None, cached=True)
                return dict(cached)
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise ProviderTimeout()
        used = 0
        while True:
            body = self._body(messages, max_tokens=max_tokens,
                              tools=tool_schemas if used < max_tool_calls else None)
            message = await self._post(body, deadline - self.clock())
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                value = self._json_content(message)
                if self.cache is not None and cached_key is not None:
                    self.cache.put(cached_key, dict(value))
                return value
            if used >= max_tool_calls:
                raise ProviderError("TOOL_BUDGET", "tool call budget exceeded")
            messages.append({"role": "assistant", "content": message.get("content") or "",
                             "tool_calls": tool_calls})
            for call in tool_calls:
                used += 1
                name = (call.get("function") or {}).get("name")
                try:
                    arguments = json.loads((call.get("function") or {}).get("arguments") or "{}")
                    result = toolbox.dispatch(name, arguments)
                except (ValueError, KeyError, TypeError) as error:
                    result = {"error": str(error)}
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                 "content": json.dumps(result, sort_keys=True, default=str)})
                if used >= max_tool_calls:
                    break
