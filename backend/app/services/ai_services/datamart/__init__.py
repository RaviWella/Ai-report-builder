"""
Datamart AI Service
===================
Text-to-SQL agent for the MintHRM warehouse database.

Uses:
  - DataHub GraphQL API for metadata-driven table discovery
  - Direct PostgreSQL introspection as fallback
  - Minchy AI proxy (OpenAI-compatible) for LLM inference
  - SQLGlot for SQL validation

Sub-modules:
  config           — configuration constants
  agent            — public async entry points (facade)
  chat_pipeline    — workspace chat (text-to-SQL + post-process)
  template_pipeline — template modification
  schema_broker    — grounded schema allowlist
  semantic_layer   — business vocabulary → warehouse mapping
  llm_client       — Minchy proxy with per-role models
"""
