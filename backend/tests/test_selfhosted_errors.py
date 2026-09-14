"""Self-hosted provider surfaces the endpoint's real error message (not a bare 400)."""
from __future__ import annotations

import httpx

from app.ai.selfhosted_provider import SelfHostedProvider, _error_detail


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status; self._payload = payload; self.text = text
    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_error_detail_openai_shape():
    r = _Resp(400, {"error": {"message": "Invalid model name passed in model=mimo-v2.5"}})
    assert "Invalid model name" in _error_detail(r)


def test_error_detail_plain_message():
    assert _error_detail(_Resp(400, {"message": "bad request"})) == "bad request"


def test_error_detail_non_json_falls_back_to_text():
    assert _error_detail(_Resp(502, None, text="upstream boom")) == "upstream boom"


def test_path_hint_only_on_404_without_v1():
    assert "add" in SelfHostedProvider._path_hint(404, "https://x.ai/chat/completions").lower()
    assert SelfHostedProvider._path_hint(404, "https://x.ai/v1/chat/completions") == ""
    assert SelfHostedProvider._path_hint(400, "https://x.ai/chat/completions") == ""


def test_max_tokens_omitted_by_default_but_sent_when_capped(monkeypatch):
    import app.ai.selfhosted_provider as sp

    captured: dict = {}

    class _FakeResp:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured.clear(); captured.update(json)
        return _FakeResp()

    monkeypatch.setattr(sp.httpx, "post", _fake_post)
    p = sp.SelfHostedProvider(base_url="http://x", model="m", api_key="k")

    # default (0 / negative / None) -> never send a non-positive max_tokens (LiteLLM 400)
    for bad in (0, -5, None):
        p._max_tokens = bad
        p._complete("s", "u")
        assert "max_tokens" not in captured

    # an explicit positive cap is sent verbatim
    p._max_tokens = 512
    p._complete("s", "u")
    assert captured["max_tokens"] == 512
