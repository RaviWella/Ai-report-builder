"""Provider factory (D9) — builds an AIProvider from a resolved config.

A resolved config carries the per-tenant choice (provider, model, decrypted key /
base URL). Swapping external <-> self-hosted is data, not code.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.base import AIProvider


@dataclass
class ResolvedAIConfig:
    provider: str  # "anthropic" | "selfhosted"
    model: str
    api_key: str | None = None  # decrypted in-memory at call time (anthropic)
    base_url: str | None = None  # self-hosted endpoint


def build_provider(config: ResolvedAIConfig) -> AIProvider:
    if config.provider == "selfhosted":
        from app.ai.selfhosted_provider import SelfHostedProvider

        return SelfHostedProvider(
            base_url=config.base_url, model=config.model, api_key=config.api_key
        )

    from app.ai.anthropic_provider import AnthropicProvider

    return AnthropicProvider(api_key=config.api_key, model=config.model)
