"""Declarative configuration schema for desktop memory providers.

Each memory provider declares its configurable surface here.  The web server
owns the generic read/write logic; this module intentionally contains only
data and lookup helpers so importing the dashboard does not load providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field

KIND_TEXT = "text"
KIND_SELECT = "select"
KIND_SECRET = "secret"


@dataclass(frozen=True)
class ProviderFieldOption:
    """A single choice for a ``select`` field."""

    value: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class ProviderField:
    """One configurable field on a declared memory provider."""

    key: str
    label: str
    kind: str = KIND_TEXT
    default: str = ""
    description: str = ""
    placeholder: str = ""
    options: tuple[ProviderFieldOption, ...] = ()
    env_key: str | None = None
    aliases: tuple[str, ...] = ()
    env_fallbacks: tuple[str, ...] = ()

    @property
    def is_secret(self) -> bool:
        return self.kind == KIND_SECRET

    def allowed_values(self) -> set[str]:
        return {opt.value for opt in self.options}


@dataclass(frozen=True)
class MemoryProvider:
    """A declared memory provider and its configurable fields."""

    name: str
    label: str
    fields: tuple[ProviderField, ...] = dataclass_field(default_factory=tuple)


HINDSIGHT = MemoryProvider(
    name="hindsight",
    label="Hindsight",
    fields=(
        ProviderField(
            key="mode",
            label="Mode",
            kind=KIND_SELECT,
            default="cloud",
            description="How Hermes connects to Hindsight.",
            options=(
                ProviderFieldOption(
                    "cloud",
                    "Cloud",
                    "Hindsight Cloud API (lightweight, just needs an API key)",
                ),
                ProviderFieldOption(
                    "local_external",
                    "Local External",
                    "Connect to an existing Hindsight instance",
                ),
            ),
        ),
        ProviderField(
            key="api_key",
            label="API key",
            kind=KIND_SECRET,
            env_key="HINDSIGHT_API_KEY",
            description="Used to authenticate with the Hindsight API.",
            placeholder="Enter Hindsight API key",
        ),
        ProviderField(
            key="api_url",
            label="API URL",
            default="https://api.hindsight.vectorize.io",
            aliases=("apiUrl",),
            env_fallbacks=("HINDSIGHT_API_URL",),
        ),
        ProviderField(
            key="bank_id",
            label="Bank ID",
            default="hermes",
            aliases=("bankId",),
        ),
        ProviderField(
            key="recall_budget",
            label="Recall budget",
            kind=KIND_SELECT,
            default="mid",
            aliases=("budget",),
            options=(
                ProviderFieldOption("low", "low"),
                ProviderFieldOption("mid", "mid"),
                ProviderFieldOption("high", "high"),
            ),
        ),
    ),
)


MEMORY_PROVIDERS: dict[str, MemoryProvider] = {
    HINDSIGHT.name: HINDSIGHT,
}


def get_memory_provider(name: str) -> MemoryProvider | None:
    """Return the declared provider for ``name``, or ``None``."""

    return MEMORY_PROVIDERS.get(name)
