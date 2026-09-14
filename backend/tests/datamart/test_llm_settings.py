"""LLM backend selection and model mapping for datamart."""
from unittest.mock import patch

from app.services.ai_services.datamart.llm.llm_settings import (
    effective_model_for_backend,
    experience_llm_backend,
    resolve_llm_connection,
)


def test_minchy_strips_ollama_model_tag():
    with patch(
        "app.services.ai_services.datamart.llm.llm_settings.settings"
    ) as mock_settings:
        mock_settings.MINCHY_AI_MODEL = "gpt-oss"
        assert effective_model_for_backend("minchy", "gpt-oss:20b") == "gpt-oss"


def test_ollama_keeps_tagged_model():
    with patch(
        "app.services.ai_services.datamart.llm.llm_settings.settings"
    ) as mock_settings:
        mock_settings.OLLAMA_MODEL = "gpt-oss:20b"
        mock_settings.EXPERIENCE_LLM_MODEL = "qwen2.5:7b"
        assert effective_model_for_backend("ollama", "gpt-oss:20b") == "gpt-oss:20b"


def test_ollama_maps_bare_gpt_oss_to_datamart_chat_model():
    with patch(
        "app.services.ai_services.datamart.config.DATAMART_CHAT_MODEL",
        "gpt-oss:20b",
    ):
        assert effective_model_for_backend("ollama", "gpt-oss") == "gpt-oss:20b"
        assert effective_model_for_backend("ollama", "") == "gpt-oss:20b"


def test_ollama_bare_gpt_oss_defaults_to_tag_when_env_untagged():
    with patch(
        "app.services.ai_services.datamart.config.DATAMART_CHAT_MODEL",
        "gpt-oss",
    ):
        with patch(
            "app.services.ai_services.datamart.llm.llm_settings.settings"
        ) as mock_settings:
            mock_settings.OLLAMA_MODEL = ""
            mock_settings.EXPERIENCE_LLM_MODEL = ""
            assert effective_model_for_backend("ollama", "gpt-oss") == "gpt-oss:20b"


def test_prefer_ollama_when_auth_configured_even_with_minchy_key():
    with patch(
        "app.services.ai_services.datamart.llm.llm_settings.settings"
    ) as mock_settings:
        mock_settings.EXPERIENCE_LLM_BACKEND = ""
        mock_settings.OLLAMA_URL = "https://ai-core.minchy.ai"
        mock_settings.OLLAMA_AUTH = "dGVzdA=="
        mock_settings.AI_PROXY_API_KEY = "sk-test"
        mock_settings.MINCHY_AI_API_KEY = ""
        assert experience_llm_backend() == "ollama"


def test_resolve_minchy_uses_proxy_model_not_tag():
    with patch(
        "app.services.ai_services.datamart.llm.llm_settings.experience_llm_backend",
        return_value="minchy",
    ):
        with patch(
            "app.services.ai_services.datamart.llm.llm_settings.effective_minchy_api_key",
            return_value="sk-test",
        ):
            with patch(
                "app.services.ai_services.datamart.llm.llm_settings.settings"
            ) as mock_settings:
                mock_settings.MINCHY_AI_BASE_URL = "https://ai-proxy.minchy.ai"
                mock_settings.MINCHY_AI_MODEL = "gpt-oss"
                mock_settings.EXPERIENCE_LLM_USER = "u"
                conn = resolve_llm_connection("gpt-oss:20b")
                assert conn.backend == "minchy"
                assert conn.model == "gpt-oss"
