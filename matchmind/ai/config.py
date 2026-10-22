"""Role C model configuration. Credentials are read from the process environment only.

Nothing here logs, echoes, persists or serialises the API key. The key never reaches
`contracts/`, an AnalysisResult, a trace note, or the frontend.
"""
import os
from dataclasses import dataclass
from pathlib import Path

# DeepSeek documents the OpenAI-format thinking toggle as a top-level body field:
#   {"thinking": {"type": "enabled" | "disabled"}}
# and thinking is ENABLED BY DEFAULT with effort "high", which does not fit the
# frozen 12 second analysis deadline. We therefore default to disabled and expose
# a single knob instead of guessing per-provider.
THINKING_STATES = ("disabled", "low", "high", "max")
ORCHESTRATORS = ("direct", "framework")
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


@dataclass(frozen=True)
class ModelConfig:
    provider: str = "mock"
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    timeout: float = 12.0
    thinking: str = "disabled"
    max_tool_calls: int = 3
    orchestrator: str = "direct"

    @property
    def configured(self) -> bool:
        """True only when a real request could actually be attempted."""
        return (self.provider not in ("", "mock")
                and self.base_url.startswith("https://")
                and "REPLACE" not in self.base_url.upper()
                and bool(self.model.strip())
                and bool(self.api_key.strip()))

    @property
    def label(self) -> str:
        return self.model.strip() or "unconfigured"

    def public(self) -> dict:
        """Deliberately excludes the key. Safe for logs, health and traces."""
        return {"provider": self.provider, "model": self.label,
                "base_url_configured": self.base_url.startswith("https://"),
                "key_present": bool(self.api_key.strip()),
                "configured": self.configured, "thinking": self.thinking,
                "orchestrator": self.orchestrator}


def _read_env_file(path=ENV_FILE) -> dict:
    """Minimal KEY=VALUE reader. Never logs values. A missing file is not an error.

    Encoding tolerance is deliberate: a teammate editing .env in Notepad on Windows can
    save UTF-16 or ANSI without noticing. Silently returning {} would downgrade a
    configured system to rule_fallback, which is honest but confusing, so we try the
    plausible encodings before giving up.
    """
    values = {}
    raw = None
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return values
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "cp936"):
        try:
            text = raw.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        return values
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if name and value:
            values[name] = value
    return values


def from_env(environ=None, *, use_env_file=True) -> ModelConfig:
    """Process environment wins; the ignored local .env only fills absent names."""
    environ = os.environ if environ is None else environ
    file_values = _read_env_file() if use_env_file else {}

    def read(name, default=""):
        value = environ.get(name)
        if value is not None and value.strip():
            return value.strip()
        return file_values.get(name, default)

    raw_timeout = read("MATCHMIND_MODEL_TIMEOUT_SEC", "12")
    try:
        timeout = float(raw_timeout)
    except ValueError:
        timeout = 12.0
    timeout = min(max(timeout, 1.0), 60.0)
    thinking = read("MATCHMIND_THINKING", "disabled").lower()
    if thinking not in THINKING_STATES:
        thinking = "disabled"
    raw_tools = read("MATCHMIND_MAX_TOOL_CALLS", "3")
    try:
        max_tool_calls = min(max(int(raw_tools), 0), 6)
    except ValueError:
        max_tool_calls = 3
    orchestrator = read("MATCHMIND_ORCHESTRATOR", "direct").lower()
    if orchestrator not in ORCHESTRATORS:
        orchestrator = "direct"
    return ModelConfig(
        provider=read("MATCHMIND_MODEL_PROVIDER", "mock"),
        base_url=read("MATCHMIND_MODEL_BASE_URL", "").rstrip("/"),
        model=read("MATCHMIND_MODEL_NAME", ""),
        api_key=read("MATCHMIND_MODEL_API_KEY", ""),
        timeout=timeout,
        thinking=thinking,
        max_tool_calls=max_tool_calls,
        orchestrator=orchestrator,
    )
