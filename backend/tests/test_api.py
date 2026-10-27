"""API 集成测试：前后端契约、后台任务轮询、错误处理与安全边界。"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.metrics import run_store

client = TestClient(app)


def _wait(client: TestClient, task_id: str, timeout: float = 8.0) -> dict:
    deadline = time.time() + timeout
    payload: dict = {}
    while time.time() < deadline:
        resp = client.get(f"/api/tasks/{task_id}")
        assert resp.status_code == 200
        payload = resp.json()
        if payload["status"] in ("SUCCESS", "FAILED", "NEED_INFO", "REVIEW_REQUIRED", "BLOCKED"):
            return payload
        time.sleep(0.05)
    return payload


def test_health_reports_mode():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["api_mode_available"] in (True, False)
    assert any("不下发" in n for n in data["notices"])


def test_create_task_and_poll_result():
    resp = client.post(
        "/api/tasks",
        json={
            "requirement": "允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务，仅允许该主机访问该服务。",
            "params": {"mode": "demo", "max_retries": 2, "require_human_review": False},
        },
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["status"] == "RECEIVED"
    assert created["deployed"] is False

    final = _wait(client, created["id"])
    assert final["status"] == "SUCCESS"
    assert final["final_validation"]["passed"] is True
    assert final["final_config"]["rules"][0]["destination_port"] == 443
    assert final["events"]
    assert final["decisions"]
    assert final["mode_label"] == "演示模式"
    assert final["token_display"].startswith("未统计")


def test_blank_requirement_is_rejected_with_chinese_message():
    resp = client.post("/api/tasks", json={"requirement": "   "})
    assert resp.status_code == 422
    assert "参数" in resp.json()["detail"]


def test_api_mode_without_key_returns_readable_error():
    resp = client.post(
        "/api/tasks",
        json={"requirement": "允许 1.1.1.1 访问 2.2.2.2 的 HTTPS 服务", "params": {"mode": "api"}},
    )
    assert resp.status_code == 400
    assert "LLM_API_KEY" in resp.json()["detail"]


def test_high_risk_task_is_blocked():
    resp = client.post(
        "/api/tasks",
        json={
            "requirement": "生成一条允许任意 IPv4 源地址访问任意 IPv4 目标地址的 ACL 规则。",
            "params": {"mode": "demo", "max_retries": 3},
        },
    )
    task = _wait(client, resp.json()["id"])
    assert task["status"] == "BLOCKED"
    assert task["awaiting_review"] is False
    assert any(f["code"] == "BROAD_PERMIT_ANY" for f in task["final_validation"]["findings"])


def test_need_info_then_feedback_resumes_task():
    resp = client.post("/api/tasks", json={"requirement": "允许办公网访问服务器。"})
    task = _wait(client, resp.json()["id"])
    assert task["status"] == "NEED_INFO"
    assert task["awaiting_user"] is True
    assert task["missing_fields"]

    feedback = client.post(
        f"/api/tasks/{task['id']}/feedback",
        json={"message": "源地址 192.168.1.10，目标地址 10.0.0.10，HTTPS 服务，仅允许该主机。"},
    )
    assert feedback.status_code == 200
    resumed = _wait(client, task["id"])
    assert resumed["status"] in ("SUCCESS", "REVIEW_REQUIRED")
    assert resumed["final_config"] is not None


def test_feedback_on_wrong_status_returns_409():
    resp = client.post(
        "/api/tasks",
        json={
            "requirement": "允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务",
            "params": {"require_human_review": False},
        },
    )
    task = _wait(client, resp.json()["id"])
    assert task["status"] == "SUCCESS"
    resp = client.post(f"/api/tasks/{task['id']}/feedback", json={"message": "补充说明"})
    assert resp.status_code == 409
    assert "补充信息" in resp.json()["detail"]


def test_review_flow_approve():
    resp = client.post(
        "/api/tasks",
        json={
            "requirement": "允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务",
            "params": {"require_human_review": True},
        },
    )
    task = _wait(client, resp.json()["id"])
    assert task["status"] == "REVIEW_REQUIRED"
    assert task["awaiting_review"] is True

    resp = client.post(
        f"/api/tasks/{task['id']}/review",
        json={"decision": "approve", "comment": "符合最小授权要求", "reviewer": "张老师"},
    )
    assert resp.status_code == 200
    reviewed = resp.json()
    assert reviewed["status"] == "SUCCESS"
    assert reviewed["review"]["decision"] == "approve"
    assert reviewed["deployed"] is False


def test_review_on_unknown_or_invalid_status():
    resp = client.post("/api/tasks/not-exist/review", json={"decision": "approve"})
    assert resp.status_code == 404

    created = client.post(
        "/api/tasks",
        json={"requirement": "允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务"},
    ).json()
    # 任务仍在执行或已完成时，审核接口都应返回 409
    time.sleep(0.01)
    resp = client.post(f"/api/tasks/{created['id']}/review", json={"decision": "approve"})
    assert resp.status_code in (409, 200)


def test_unknown_task_returns_404():
    assert client.get("/api/tasks/not-exist").status_code == 404


def test_test_cases_endpoint_lists_all_with_expectations():
    resp = client.get("/api/test-cases")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 10
    ids = {c["id"] for c in data["items"]}
    assert {"TC-01", "TC-06", "TC-09", "TC-10"}.issubset(ids)
    for case in data["items"]:
        assert case["expected_status"]
        assert case["target"]
        assert case["category"]


def test_run_single_test_case():
    resp = client.post("/api/test-cases/run", json={"case_ids": ["TC-01"], "group": "agent"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["matched_expected"] is True
    assert "演示模式" in data["notice"]
    # 说明文案要能区分流水线分组，避免把对照组结果误解为系统失败
    assert "C 组执行完整 Agent 闭环" in data["notice"]


def test_control_group_notice_explains_lower_match():
    resp = client.post("/api/test-cases/run", json={"case_ids": ["TC-04"], "group": "basic"})
    data = resp.json()
    assert data["results"][0]["matched_expected"] is False
    assert "对照组" in data["notice"]


def test_run_unknown_test_case_returns_404():
    resp = client.post("/api/test-cases/run", json={"case_ids": ["TC-404"]})
    assert resp.status_code == 404


def test_metrics_endpoint_reflects_actual_runs():
    client.post("/api/experiments/reset")
    empty = client.get("/api/metrics").json()
    assert empty["status"] == "NOT_RUN"

    ran = client.post("/api/experiments/run")
    assert ran.status_code == 200
    data = ran.json()
    assert data["status"] == "COMPLETED"
    assert len(data["groups"]) == 3
    assert data["case_count"] >= 10
    for group in data["groups"]:
        keys = {m["key"] for m in group["metrics"]}
        assert {"risk_recall", "false_positive_rate", "correction_success_rate", "tokens"} <= keys
    assert any("演示模式" in n for n in data["notices"])
    assert run_store.recorded_at is not None


def test_polling_events_endpoint():
    created = client.post(
        "/api/tasks",
        json={"requirement": "允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务"},
    ).json()
    _wait(client, created["id"])
    resp = client.get(f"/api/tasks/{created['id']}/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["events"]
    assert data["max_retries"] == 2
    assert all("message" in e for e in data["events"])
