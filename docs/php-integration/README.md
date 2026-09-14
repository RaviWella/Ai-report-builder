# PHP / HRIS integration — moved

Report Builder SSO and refresh-token integration live in the **HRIS** repo, not here.

**HRIS path:** `/Applications/XAMPP/xamppfiles/htdocs/HRIS`

| What | Where in HRIS |
|------|-----------------|
| SSO component | `protected/components/ReportBuilderSso.php` |
| Config | `protected/config/main.php` → `params.reportBuilder` |
| Builder entry (Template tile) | `protected/controllers/SettingController.php` → `actionTemplate()` |
| Refresh API | `protected/controllers/ApiV1Controller.php` → `actionReportBuilderExtendSession()` |
| DB migration | `db_changes/report_builder_user_session_bindings.sql` |
| Documentation | `docs/report-builder-integration/README.md` |

## Refresh flow (this repo)

| Piece | Location |
|-------|----------|
| BFF refresh endpoint | `backend/app/api/v1/auth.py` → `POST /auth/refresh` |
| HRIS proxy | `backend/app/services/hris_refresh.py` |
| SPA refresh + 401 retry | `frontend/src/auth/refresh.ts`, `frontend/src/api/client.ts` |
| Session handoff | `frontend/src/auth/session.ts` |

Refresh tries the customer HRIS first. If that call fails for infrastructure reasons (unreachable, CSRF, missing Authorization header), Report Builder **reissues the JWT locally** for up to 24 hours from original `auth_time`. HRIS logout (`version mismatch`) still ends the session.

Env (Report Builder):

- `JWT_ACCESS_TTL_SECONDS=900`
- `JWT_REFRESH_LEEWAY_SECONDS=86400` (must cover idle time while the HRIS PHP session is still valid)

For local JWT testing without HRIS, use `gen_token.py` in this folder (Python stdlib only).
Tokens without `hris_origin`/`sid`/`ver` cannot be refreshed — only used for dev API smoke tests.
