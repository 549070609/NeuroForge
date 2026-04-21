"""P0-8 Auth 时序安全 + 多 key 回归测试"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from Service.config.settings import ServiceSettings
from Service.gateway.middleware.auth import AuthMiddleware, _hash_key


def _make_app(settings: ServiceSettings) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware, settings=settings)

    @app.get("/private")
    async def _private(request: Request):
        client_id = getattr(request.state, "client_id", None)
        return {"ok": True, "client_id": client_id}

    @app.get("/health")
    async def _health():
        return {"status": "ok"}

    return app


class TestSingleKey:
    def test_missing_key_401(self):
        settings = ServiceSettings(api_key="secret")
        client = TestClient(_make_app(settings), raise_server_exceptions=False)
        resp = client.get("/private")
        assert resp.status_code == 401

    def test_wrong_key_403(self):
        settings = ServiceSettings(api_key="secret")
        client = TestClient(_make_app(settings), raise_server_exceptions=False)
        resp = client.get("/private", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 403

    def test_correct_key_ok_with_default_client_id(self):
        settings = ServiceSettings(api_key="secret")
        client = TestClient(_make_app(settings), raise_server_exceptions=False)
        resp = client.get("/private", headers={"X-API-Key": "secret"})
        assert resp.status_code == 200
        assert resp.json()["client_id"] == "default"

    def test_public_path_bypasses_auth(self):
        settings = ServiceSettings(api_key="secret")
        client = TestClient(_make_app(settings), raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200


class TestMultiKey:
    def test_multi_key_each_resolves_own_client_id(self):
        settings = ServiceSettings(
            api_keys={"k-alpha": "alpha", "k-beta": "beta"}
        )
        client = TestClient(_make_app(settings), raise_server_exceptions=False)

        r1 = client.get("/private", headers={"X-API-Key": "k-alpha"})
        assert r1.status_code == 200
        assert r1.json()["client_id"] == "alpha"

        r2 = client.get("/private", headers={"X-API-Key": "k-beta"})
        assert r2.status_code == 200
        assert r2.json()["client_id"] == "beta"

    def test_unknown_key_403_even_with_multi_key(self):
        settings = ServiceSettings(api_keys={"k-alpha": "alpha"})
        client = TestClient(_make_app(settings), raise_server_exceptions=False)
        resp = client.get("/private", headers={"X-API-Key": "bogus"})
        assert resp.status_code == 403

    def test_api_keys_takes_precedence_over_api_key(self):
        """同时配置时 api_keys 生效。"""
        settings = ServiceSettings(
            api_key="legacy",
            api_keys={"k-new": "new"},
        )
        client = TestClient(_make_app(settings), raise_server_exceptions=False)

        # legacy key 应被拒绝（api_keys 接管）
        r_legacy = client.get("/private", headers={"X-API-Key": "legacy"})
        assert r_legacy.status_code == 403

        r_new = client.get("/private", headers={"X-API-Key": "k-new"})
        assert r_new.status_code == 200


class TestNoAuthConfigured:
    def test_no_key_configured_allows_through(self):
        """向后兼容：未配置任何 key 时跳过认证。"""
        settings = ServiceSettings()  # api_key=None, api_keys={}
        client = TestClient(_make_app(settings), raise_server_exceptions=False)
        resp = client.get("/private")
        assert resp.status_code == 200


class TestTimingSafety:
    """compare_digest 使用：确保等长 hash 比较（不验证实际 timing，仅验证接口）。"""

    def test_hash_key_produces_fixed_length(self):
        short = _hash_key("a")
        long = _hash_key("a" * 1000)
        assert len(short) == len(long) == 32  # SHA-256
