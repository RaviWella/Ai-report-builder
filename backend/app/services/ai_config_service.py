"""AI provider configuration service (SRS §8.4, §9)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.factory import ResolvedAIConfig
from app.core.config import settings
from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.db.metadata import AIProviderConfig
from app.db.platform_models import SystemAIProviderConfig
from app.db.postgres import get_postgres_database


@dataclass
class PublicAIConfig:
    provider: str
    model: str
    base_url: str | None
    enabled: bool
    has_api_key: bool
    api_key_hint: str
    source: str  # "tenant" | "system" | "env-default"


class AIConfigService:
    def __init__(self, db: Session):
        self.db = db

    def _tenant_row(self) -> AIProviderConfig | None:
        return self.db.execute(select(AIProviderConfig).limit(1)).scalar_one_or_none()

    def _system_row(self) -> SystemAIProviderConfig | None:
        pg = get_postgres_database().session()
        try:
            pg.execute(text("SET search_path TO platform, public"))
            return pg.get(SystemAIProviderConfig, "system")
        finally:
            pg.close()

    def _env_api_key_for(self, provider: str) -> str:
        if provider == "selfhosted":
            return settings.selfhosted_api_key
        return settings.anthropic_api_key

    def upsert(
        self,
        tenant_id: str,
        *,
        provider: str,
        model: str,
        updated_by: str,
        api_key: str | None = None,
        base_url: str | None = None,
        enabled: bool = True,
    ) -> PublicAIConfig:
        row = self._tenant_row()
        if row is None:
            row = AIProviderConfig(updated_by=updated_by)
            self.db.add(row)
        row.provider = provider
        row.model = model
        row.base_url = base_url
        row.enabled = enabled
        row.updated_by = updated_by
        if api_key:
            row.api_key_encrypted = encrypt_secret(api_key)
        self.db.commit()
        return self.public(tenant_id)

    def public(self, tenant_id: str) -> PublicAIConfig:
        row = self._tenant_row()
        source = "tenant" if row else ("system" if self._system_row() else "env-default")
        if row is None:
            sys_row = self._system_row()
            if sys_row is None:
                api_key = self._env_api_key_for(settings.ai_provider)
                return PublicAIConfig(
                    provider=settings.ai_provider, model=settings.ai_model, base_url=None,
                    enabled=True, has_api_key=bool(api_key),
                    api_key_hint=mask_secret(api_key), source="env-default",
                )
            row = sys_row
        hint = ""
        if row.api_key_encrypted:
            try:
                hint = mask_secret(decrypt_secret(row.api_key_encrypted))
            except Exception:
                hint = "…"
        return PublicAIConfig(
            provider=row.provider, model=row.model, base_url=row.base_url,
            enabled=row.enabled, has_api_key=bool(row.api_key_encrypted),
            api_key_hint=hint, source=source,
        )

    def resolve(self, tenant_id: str) -> ResolvedAIConfig:
        row = self._tenant_row() or self._system_row()
        if row is None:
            api_key = self._env_api_key_for(settings.ai_provider)
            return ResolvedAIConfig(
                provider=settings.ai_provider, model=settings.ai_model,
                api_key=api_key or None,
                base_url=settings.selfhosted_base_url,
            )
        key = decrypt_secret(row.api_key_encrypted) if row.api_key_encrypted else (
            self._env_api_key_for(row.provider) or None
        )
        return ResolvedAIConfig(
            provider=row.provider, model=row.model, api_key=key, base_url=row.base_url
        )
