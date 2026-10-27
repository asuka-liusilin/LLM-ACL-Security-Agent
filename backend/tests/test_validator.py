"""校验模块单元测试：结构、字段值、授权范围、高风险规则。"""

from __future__ import annotations

import json

from app.intent_parser import parse_intent
from app.schemas import Intent, TaskParams
from app.validator import validate_config


def _report(config, requirement: str | None = None, **params):
    intent = parse_intent(requirement) if requirement else None
    return validate_config(json.dumps(config, ensure_ascii=False), intent, TaskParams(**params))


GOOD = {
    "rules": [
        {
            "action": "permit",
            "protocol": "tcp",
            "source": "192.168.1.10/32",
            "destination": "10.0.0.10/32",
            "destination_port": 443,
        }
    ],
    "default_action": "deny",
}
REQ = "允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务，仅允许该主机访问该服务。"


def test_valid_config_passes_all_checks():
    report = _report(GOOD, REQ)
    assert report.passed is True
    assert report.config_parsed is True
    assert report.findings == []
    assert [c.status for c in report.checks] == ["PASS", "PASS", "PASS", "PASS"]


def test_invalid_json_is_rejected():
    report = validate_config('{"rules": [', None, TaskParams())
    assert report.passed is False
    assert report.config_parsed is False
    assert "JSON_PARSE_ERROR" in report.codes()
    # 无法解析时，其余检查必须标记为“无法判断”，而不是默认通过
    assert [c.status for c in report.checks[1:]] == ["UNDETERMINED"] * 3


def test_missing_rules_field():
    report = _report({"default_action": "deny"}, REQ)
    assert "MISSING_RULES" in report.codes()
    assert report.passed is False


def test_rule_missing_required_field():
    config = {
        "rules": [{"action": "permit", "protocol": "tcp", "source": "192.168.1.10/32"}],
        "default_action": "deny",
    }
    report = _report(config, REQ)
    assert "RULE_MISSING_FIELD" in report.codes()
    assert any("destination" in f.message for f in report.findings)


def test_invalid_ip_address_detected():
    config = {
        "rules": [
            {
                "action": "permit",
                "protocol": "tcp",
                "source": "192.168.1.300/32",
                "destination": "10.0.0.10/32",
                "destination_port": 443,
            }
        ],
        "default_action": "deny",
    }
    report = _report(config, REQ)
    assert "INVALID_SOURCE_IP" in report.codes()
    assert report.passed is False


def test_invalid_cidr_prefix_detected():
    config = {
        "rules": [
            {
                "action": "permit",
                "protocol": "tcp",
                "source": "192.168.1.0/33",
                "destination": "10.0.0.10/32",
                "destination_port": 443,
            }
        ],
        "default_action": "deny",
    }
    report = _report(config, REQ)
    assert "INVALID_SOURCE_IP" in report.codes()


def test_host_bits_set_in_cidr_is_rejected():
    """192.168.1.10/24 这种“主机位非零”的写法应当被拒绝，避免掩盖真实网段。"""
    config = {
        "rules": [
            {
                "action": "permit",
                "protocol": "tcp",
                "source": "192.168.1.10/24",
                "destination": "10.0.0.10/32",
                "destination_port": 443,
            }
        ],
        "default_action": "deny",
    }
    report = _report(config, REQ)
    assert "INVALID_SOURCE_IP" in report.codes()


def test_invalid_action_and_protocol():
    config = {
        "rules": [
            {
                "action": "allow",
                "protocol": "https",
                "source": "192.168.1.10/32",
                "destination": "10.0.0.10/32",
            }
        ],
        "default_action": "drop",
    }
    report = _report(config, REQ)
    codes = set(report.codes())
    assert {"INVALID_ACTION", "INVALID_PROTOCOL", "INVALID_DEFAULT_ACTION"} <= codes


def test_source_scope_exceeded():
    config = {
        "rules": [
            {
                "action": "permit",
                "protocol": "tcp",
                "source": "192.168.1.0/24",
                "destination": "10.0.0.10/32",
                "destination_port": 443,
            }
        ],
        "default_action": "deny",
    }
    report = _report(config, REQ)
    assert "SOURCE_SCOPE_EXCEEDED" in report.codes()
    finding = next(f for f in report.findings if f.code == "SOURCE_SCOPE_EXCEEDED")
    assert finding.severity == "HIGH"
    assert finding.retryable is True
    assert "192.168.1.0/24" in finding.evidence


def test_destination_scope_exceeded():
    config = {
        "rules": [
            {
                "action": "permit",
                "protocol": "tcp",
                "source": "192.168.1.10/32",
                "destination": "10.0.0.0/24",
                "destination_port": 443,
            }
        ],
        "default_action": "deny",
    }
    report = _report(config, REQ)
    assert "DESTINATION_SCOPE_EXCEEDED" in report.codes()


def test_narrower_scope_is_allowed():
    """比授权范围更小的规则不应被误报。"""
    config = {
        "rules": [
            {
                "action": "permit",
                "protocol": "tcp",
                "source": "192.168.1.10/32",
                "destination": "10.0.0.10/32",
                "destination_port": 443,
            }
        ],
        "default_action": "deny",
    }
    report = _report(config, REQ)
    assert report.passed is True
    assert report.findings == []


def test_broad_permit_any_is_blocking_critical():
    config = {
        "rules": [
            {"action": "permit", "protocol": "ip", "source": "0.0.0.0/0", "destination": "0.0.0.0/0"}
        ],
        "default_action": "deny",
    }
    report = _report(config, "生成一条允许任意 IPv4 源地址访问任意 IPv4 目标地址的 ACL 规则。")
    finding = next(f for f in report.findings if f.code == "BROAD_PERMIT_ANY")
    assert finding.severity == "CRITICAL"
    assert finding.blocking is True
    assert finding.retryable is False
    assert report.status_suggestion == "BLOCKED"


def test_default_permit_is_high_risk():
    config = json.loads(json.dumps(GOOD))
    config["default_action"] = "permit"
    report = _report(config, "允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务，其他未授权流量默认拒绝。")
    assert "DEFAULT_PERMIT" in report.codes()
    assert "DEFAULT_ACTION_MISMATCH" in report.codes()


def test_action_contradicts_intent():
    config = {
        "rules": [
            {
                "action": "deny",
                "protocol": "tcp",
                "source": "192.168.1.10/32",
                "destination": "10.0.0.10/32",
                "destination_port": 443,
            }
        ],
        "default_action": "deny",
    }
    report = _report(config, REQ)
    assert "ACTION_CONTRADICTS_INTENT" in report.codes()


def test_unknown_field_is_low_severity():
    config = json.loads(json.dumps(GOOD))
    config["rules"][0]["mystery"] = "x"
    report = _report(config, REQ)
    finding = next(f for f in report.findings if f.code == "UNKNOWN_FIELD")
    assert finding.severity == "LOW"
    # 仅低风险提示，不应阻止通过
    assert report.passed is True


def test_intent_undetermined_when_requirement_incomplete():
    intent = parse_intent("允许办公网访问服务器。")
    report = validate_config(json.dumps(GOOD), intent, TaskParams())
    check_c = next(c for c in report.checks if c.key == "C")
    assert check_c.status == "UNDETERMINED"
    # 无法判断需求符合度时，不能声称“已验证需求”
    assert "无法" in check_c.summary


def test_ipv6_rejected_by_model_constraint():
    config = {
        "rules": [
            {
                "action": "permit",
                "protocol": "tcp",
                "source": "2001:db8::1/128",
                "destination": "10.0.0.10/32",
                "destination_port": 443,
            }
        ],
        "default_action": "deny",
    }
    report = _report(config, REQ)
    assert "IP_VERSION_MISMATCH" in report.codes()


def test_empty_rules_is_flagged():
    report = _report({"rules": [], "default_action": "deny"}, REQ)
    assert "EMPTY_RULES" in report.codes()
    assert report.passed is False


def test_validator_does_not_claim_absolute_security():
    """校验通过的说明文字必须保留“不代表绝对安全”的限定。"""
    report = _report(GOOD, REQ)
    check_d = next(c for c in report.checks if c.key == "D")
    assert "不代表绝对安全" in check_d.summary
