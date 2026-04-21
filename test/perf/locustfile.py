"""P1-12 压测脚本骨架 — 需要本地启动 Service 后通过 locust 运行。

用法::

    uvicorn Service.gateway.app:create_app --factory --port 8000 &
    locust -f test/perf/locustfile.py --host http://localhost:8000 \\
        --users 50 --spawn-rate 5 --run-time 60s --headless
"""

from __future__ import annotations

from locust import HttpUser, between, task  # type: ignore[import-not-found]


class NeuroForgeUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(3)
    def list_agents(self) -> None:
        self.client.get("/api/agents")

    @task(1)
    def list_namespaces(self) -> None:
        self.client.get("/api/agents/namespaces")

    @task(1)
    def health(self) -> None:
        self.client.get("/health")
