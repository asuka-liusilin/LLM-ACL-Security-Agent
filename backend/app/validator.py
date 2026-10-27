"""ACL 配置独立校验模块。

只依赖 Python 标准库（json / ipaddress / re），不调用任何模型，
因此其结论独立于“配置是由谁生成的”。

四个维度：
  A. JSON 结构与字段完整性
  B. 字段值合法性（动作 / 协议 / IP / CIDR / 端口 / 默认策略）
  C. 授权范围符合度（与用户原始需求比较）
  D. 预定义高风险规则

注意：校验通过只代表“未命中已实现的检查项”，不代表配置绝对安全。
ACL 规则顺序、应用位置、设备语义等不在本原型覆盖范围内。
"""

from __future__ import annotations

import ipaddress
import json
import re
from typing import Any, Optional

from .schemas import (
    CheckResult,
    CheckStatus,
    Finding,
    Intent,
    SEVERITY_ORDER,
    TaskParams,
    ValidationReport,
)
from .states import TaskStatus

ALLOWED_FIELDS = {"action", "protocol", "source", "destination", "destination_port", "description"}
REQUIRED_FIELDS = ("action", "protocol", "source", "destination")
ALLOWED_ACTIONS = {"permit", "deny"}
ALLOWED_PROTOCOLS = {"tcp", "udp", "icmp", "ip"}
ANY_NET = ipaddress.ip_network("0.0.0.0/0")


def _finding(
    code: str,
    severity: str,
    dimension: str,
    message: str,
    evidence: str = "",
    recommendation: str = "",
    retryable: bool = False,
    blocking: bool = False,
) -> Finding:
    return Finding(
        code=code,
        severity=severity,  # type: ignore[arg-type]
        dimension=dimension,  # type: ignore[arg-type]
        message=message,
        evidence=evidence,
        recommendation=recommendation,
        retryable=retryable,
        blocking=blocking,
    )


def parse_network(value: Any) -> tuple[Optional[ipaddress._BaseNetwork], Optional[str]]:
    """把字符串解析成网络对象。不带前缀时按单主机 /32 处理。"""
    if not isinstance(value, str):
        return None, "不是字符串"
    token = value.strip()
    if not token:
        return None, "空字符串"
    try:
        if "/" in token:
            return ipaddress.ip_network(token, strict=True), None
        addr = ipaddress.ip_address(token)
        return ipaddress.ip_network(f"{addr}/{addr.max_prefixlen}"), None
    except ValueError as exc:
        return None, str(exc)


def _safe_subnet_of(child: ipaddress._BaseNetwork, parent: ipaddress._BaseNetwork) -> bool:
    if child.version != parent.version:
        return False
    return child.subnet_of(parent)  # type: ignore[arg-type]


def _safe_overlaps(a: ipaddress._BaseNetwork, b: ipaddress._BaseNetwork) -> bool:
    if a.version != b.version:
        return False
    return a.overlaps(b)  # type: ignore[arg-type]


def _check_structure(config: Any) -> tuple[list[Finding], bool, list[dict[str, Any]]]:
    findings: list[Finding] = []
    if not isinstance(config, dict):
        findings.append(
            _finding(
                "ROOT_NOT_OBJECT",
                "CRITICAL",
                "structure",
                "JSON 根节点必须是对象（包含 rules 与 default_action）。",
                f"实际类型为 {type(config).__name__}",
                "按统一数据模型重新生成配置。",
            )
        )
        return findings, False, []

    if "rules" not in config:
        findings.append(
            _finding(
                "MISSING_RULES",
                "CRITICAL",
                "structure",
                "配置缺少 rules 字段。",
                "顶层键：" + ", ".join(sorted(config.keys())) if config else "顶层为空",
                "补充 rules 列表后重新校验。",
            )
        )
        return findings, False, []

    rules = config["rules"]
    if not isinstance(rules, list):
        findings.append(
            _finding(
                "RULES_NOT_LIST",
                "CRITICAL",
                "structure",
                "rules 字段必须是数组。",
                f"实际类型为 {type(rules).__name__}",
                "修正为规则数组。",
            )
        )
        return findings, False, []

    if len(rules) == 0:
        findings.append(
            _finding(
                "EMPTY_RULES",
                "HIGH",
                "structure",
                "rules 为空数组，没有可用的访问控制规则。",
                "rules = []",
                "根据需求补充至少一条规则，或说明为何不需要规则。",
            )
        )

    if "default_action" not in config:
        findings.append(
            _finding(
                "MISSING_DEFAULT_ACTION",
                "HIGH",
                "structure",
                "配置缺少 default_action 字段，默认策略不明确。",
                "顶层键：" + ", ".join(sorted(config.keys())),
                "显式声明默认策略（deny 为最小权限选择）。",
            )
        )

    valid_rules: list[dict[str, Any]] = []
    seen_codes: set[tuple[str, str]] = set()

    def add(item: Finding) -> None:
        key = (item.code, item.evidence)
        if key not in seen_codes:
            seen_codes.add(key)
            findings.append(item)

    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            add(
                _finding(
                    "RULE_NOT_OBJECT",
                    "HIGH",
                    "structure",
                    f"第 {index + 1} 条规则不是对象。",
                    f"实际类型为 {type(rule).__name__}",
                    "每条规则应为包含 action/protocol/source/destination 的对象。",
                )
            )
            continue

        missing = [f for f in REQUIRED_FIELDS if f not in rule]
        if missing:
            add(
                _finding(
                    "RULE_MISSING_FIELD",
                    "HIGH",
                    "structure",
                    f"第 {index + 1} 条规则缺少必要字段：{', '.join(missing)}。",
                    json.dumps(rule, ensure_ascii=False),
                    "补齐必要字段后重新生成或手工修正。",
                    retryable=True,
                )
            )

        extra = [f for f in rule if f not in ALLOWED_FIELDS]
        if extra:
            add(
                _finding(
                    "UNKNOWN_FIELD",
                    "LOW",
                    "structure",
                    f"第 {index + 1} 条规则包含数据模型之外的字段：{', '.join(extra)}。",
                    json.dumps({k: rule[k] for k in extra}, ensure_ascii=False),
                    "删除额外字段，或先扩展统一数据模型再使用。",
                )
            )

        type_problem = False
        for field in ("action", "protocol", "source", "destination"):
            if field in rule and not isinstance(rule[field], str):
                type_problem = True
                add(
                    _finding(
                        "RULE_FIELD_TYPE_INVALID",
                        "HIGH",
                        "structure",
                        f"第 {index + 1} 条规则的 {field} 字段类型应为字符串。",
                        f"{field} = {json.dumps(rule[field], ensure_ascii=False)}",
                        "修正字段类型。",
                        retryable=True,
                    )
                )
        if "destination_port" in rule:
            port = rule["destination_port"]
            if port is not None and (isinstance(port, bool) or not isinstance(port, int)):
                type_problem = True
                add(
                    _finding(
                        "RULE_FIELD_TYPE_INVALID",
                        "HIGH",
                        "structure",
                        f"第 {index + 1} 条规则的 destination_port 应为整数或 null。",
                        f"destination_port = {json.dumps(port, ensure_ascii=False)}",
                        "修正端口类型。",
                        retryable=True,
                    )
                )
        if "description" in rule and rule["description"] is not None and not isinstance(
            rule["description"], str
        ):
            add(
                _finding(
                    "RULE_FIELD_TYPE_INVALID",
                    "LOW",
                    "structure",
                    f"第 {index + 1} 条规则的 description 应为字符串。",
                    f"description = {json.dumps(rule['description'], ensure_ascii=False)}",
                    "修正字段类型。",
                )
            )

        if not missing and not type_problem:
            valid_rules.append(rule)

    structure_ok = not any(f.severity in ("HIGH", "CRITICAL") for f in findings) and not any(
        f.code in ("ROOT_NOT_OBJECT", "MISSING_RULES", "RULES_NOT_LIST") for f in findings
    )
    return findings, structure_ok, valid_rules


def _check_values(
    config: dict[str, Any], rules: list[dict[str, Any]]
) -> tuple[list[Finding], list[dict[str, Any]]]:
    """字段值检查。返回 (findings, 可用于后续语义检查的规则列表)。"""
    findings: list[Finding] = []
    checked: list[dict[str, Any]] = []

    default_action = config.get("default_action")
    if default_action is not None and default_action not in ALLOWED_ACTIONS:
        findings.append(
            _finding(
                "INVALID_DEFAULT_ACTION",
                "HIGH",
                "value",
                "default_action 只能是 permit 或 deny。",
                f"default_action = {json.dumps(default_action, ensure_ascii=False)}",
                "改为 deny（最小权限）或 permit，并说明理由。",
                retryable=True,
            )
        )

    for index, rule in enumerate(rules):
        rule_no = index + 1
        ok = True

        action = rule.get("action")
        if action not in ALLOWED_ACTIONS:
            ok = False
            findings.append(
                _finding(
                    "INVALID_ACTION",
                    "HIGH",
                    "value",
                    f"第 {rule_no} 条规则的 action 取值不合法。",
                    f"action = {json.dumps(action, ensure_ascii=False)}，允许值：permit / deny",
                    "改为 permit 或 deny。",
                    retryable=True,
                )
            )

        protocol = rule.get("protocol")
        if protocol not in ALLOWED_PROTOCOLS:
            ok = False
            findings.append(
                _finding(
                    "INVALID_PROTOCOL",
                    "HIGH",
                    "value",
                    f"第 {rule_no} 条规则的 protocol 取值不合法。",
                    f"protocol = {json.dumps(protocol, ensure_ascii=False)}，允许值：{', '.join(sorted(ALLOWED_PROTOCOLS))}",
                    "改为数据模型允许的协议。",
                    retryable=True,
                )
            )

        src_net = dst_net = None
        for field, label, code in (
            ("source", "源地址", "INVALID_SOURCE_IP"),
            ("destination", "目标地址", "INVALID_DESTINATION_IP"),
        ):
            net, err = parse_network(rule.get(field))
            if net is None:
                ok = False
                findings.append(
                    _finding(
                        code,
                        "HIGH",
                        "value",
                        f"第 {rule_no} 条规则的{label}不是合法的 IP 地址或 CIDR。",
                        f"{field} = {json.dumps(rule.get(field), ensure_ascii=False)}；解析错误：{err}",
                        "改为合法的 IPv4 地址或 CIDR，例如 192.168.1.10 或 192.168.1.0/24。",
                        retryable=True,
                    )
                )
            else:
                if net.version != 4:
                    ok = False
                    findings.append(
                        _finding(
                            "IP_VERSION_MISMATCH",
                            "HIGH",
                            "value",
                            f"第 {rule_no} 条规则的{label}为 IPv6，而当前数据模型只支持 IPv4。",
                            f"{field} = {rule.get(field)}",
                            "当前版本仅支持 IPv4；需要 IPv6 时应扩展数据模型。",
                            retryable=True,
                        )
                    )
                elif field == "source":
                    src_net = net
                else:
                    dst_net = net

        port = rule.get("destination_port")
        if port is not None and isinstance(port, int) and not isinstance(port, bool):
            if port < 1 or port > 65535:
                ok = False
                findings.append(
                    _finding(
                        "INVALID_PORT",
                        "HIGH",
                        "value",
                        f"第 {rule_no} 条规则的 destination_port 超出 1-65535 范围。",
                        f"destination_port = {port}",
                        "修正为合法端口号。",
                        retryable=True,
                    )
                )
            if protocol in ("icmp", "ip"):
                findings.append(
                    _finding(
                        "PORT_PROTOCOL_MISMATCH",
                        "MEDIUM",
                        "value",
                        f"第 {rule_no} 条规则指定了端口，但协议为 {protocol}，端口约束不适用。",
                        f"protocol = {protocol}, destination_port = {port}",
                        "删除端口或改用 tcp/udp 协议。",
                        retryable=True,
                    )
                )
        elif port is None and protocol in ("tcp", "udp"):
            findings.append(
                _finding(
                    "PORT_UNSPECIFIED",
                    "INFO",
                    "value",
                    f"第 {rule_no} 条规则协议为 {protocol} 但未限定端口，等价于放行该协议全部端口。",
                    f"protocol = {protocol}, destination_port = null",
                    "如需求只涉及特定服务，应补充端口以免范围扩大。",
                )
            )

        if ok and src_net is not None and dst_net is not None:
            checked.append({**rule, "_src": src_net, "_dst": dst_net, "_index": index})

    return findings, checked


def _check_intent(intent: Optional[Intent], rules: list[dict[str, Any]]) -> tuple[list[Finding], CheckStatus]:
    if intent is None:
        return [], CheckStatus.UNDETERMINED
    if not intent.is_complete:
        return [], CheckStatus.UNDETERMINED

    auth_src, _ = parse_network(intent.sources[0]) if intent.sources else (None, None)
    auth_dst, _ = parse_network(intent.destinations[0]) if intent.destinations else (None, None)
    if auth_src is None or auth_dst is None:
        return [], CheckStatus.UNDETERMINED

    findings: list[Finding] = []

    for rule in rules:
        idx = rule.get("_index", 0) + 1
        src, dst = rule["_src"], rule["_dst"]
        action = rule["action"]

        if action == "permit":
            if not _safe_subnet_of(src, auth_src):
                if _safe_overlaps(src, auth_src):
                    findings.append(
                        _finding(
                            "SOURCE_SCOPE_EXCEEDED",
                            "HIGH",
                            "intent",
                            f"第 {idx} 条规则的源地址范围超出用户授权范围。",
                            f"生成范围 {src}，用户要求 {auth_src}。",
                            "重新生成仅覆盖授权范围的规则，或交由人工审核确认。",
                            retryable=True,
                        )
                    )
                else:
                    findings.append(
                        _finding(
                            "SOURCE_OUTSIDE_INTENT",
                            "HIGH",
                            "intent",
                            f"第 {idx} 条规则的源地址与用户授权范围不重叠。",
                            f"生成范围 {src}，用户要求 {auth_src}。",
                            "重新生成与需求一致的源地址。",
                            retryable=True,
                        )
                    )
            if not _safe_subnet_of(dst, auth_dst):
                if _safe_overlaps(dst, auth_dst):
                    findings.append(
                        _finding(
                            "DESTINATION_SCOPE_EXCEEDED",
                            "HIGH",
                            "intent",
                            f"第 {idx} 条规则的目标地址范围超出用户授权范围。",
                            f"生成范围 {dst}，用户要求 {auth_dst}。",
                            "重新生成仅覆盖授权范围的目标地址，或交由人工审核确认。",
                            retryable=True,
                        )
                    )
                else:
                    findings.append(
                        _finding(
                            "DESTINATION_OUTSIDE_INTENT",
                            "HIGH",
                            "intent",
                            f"第 {idx} 条规则的目标地址与用户授权范围不重叠。",
                            f"生成范围 {dst}，用户要求 {auth_dst}。",
                            "重新生成与需求一致的目标地址。",
                            retryable=True,
                        )
                    )

            if intent.protocol and intent.protocol != "ip":
                if rule["protocol"] == "ip":
                    findings.append(
                        _finding(
                            "PROTOCOL_SCOPE_EXPANDED",
                            "MEDIUM",
                            "intent",
                            f"第 {idx} 条规则放行了全部协议，而需求只涉及 {intent.protocol.upper()}。",
                            f"生成 protocol = ip，需求 protocol = {intent.protocol}",
                            "限定协议为需求指定的协议。",
                            retryable=True,
                        )
                    )
                elif rule["protocol"] != intent.protocol:
                    findings.append(
                        _finding(
                            "PROTOCOL_MISMATCH",
                            "HIGH",
                            "intent",
                            f"第 {idx} 条规则的协议与需求不一致。",
                            f"生成 protocol = {rule['protocol']}，需求 protocol = {intent.protocol}",
                            "按需求协议重新生成。",
                            retryable=True,
                        )
                    )

            if intent.destination_port is not None and rule.get("destination_port") != intent.destination_port:
                findings.append(
                    _finding(
                        "PORT_SCOPE_EXPANDED",
                        "HIGH",
                        "intent",
                        f"第 {idx} 条规则的目标端口范围与需求不一致（未限定端口等于放行全部端口）。",
                        f"生成 destination_port = {rule.get('destination_port')}，需求为 {intent.destination_port}",
                        "补充与需求一致的目标端口。",
                        retryable=True,
                    )
                )

    # 动作是否与需求相反
    if intent.action == "permit":
        # 只要存在“覆盖了授权范围”的放行规则，就不算动作相反（范围问题由上面的检查单独报告）
        covering = [
            r
            for r in rules
            if r["action"] == "permit"
            and _safe_subnet_of(auth_src, r["_src"])
            and _safe_subnet_of(auth_dst, r["_dst"])
        ]
        if not covering:
            findings.append(
                _finding(
                    "ACTION_CONTRADICTS_INTENT",
                    "HIGH",
                    "intent",
                    "配置中没有与需求匹配的放行规则，需求要求允许访问。",
                    f"需求动作 permit，规则动作：{sorted({r['action'] for r in rules}) or '空'}",
                    "按需求生成 permit 规则。",
                    retryable=True,
                )
            )
    elif intent.action == "deny":
        permitting = [
            r
            for r in rules
            if r["action"] == "permit"
            and _safe_overlaps(r["_src"], auth_src)
            and _safe_overlaps(r["_dst"], auth_dst)
        ]
        if permitting:
            findings.append(
                _finding(
                    "ACTION_CONTRADICTS_INTENT",
                    "HIGH",
                    "intent",
                    "需求要求拒绝该访问，但配置中存在放行规则。",
                    f"命中放行规则 {len(permitting)} 条，需求动作 deny",
                    "改为 deny，或交由人工审核确认。",
                    retryable=True,
                )
            )

    return findings, CheckStatus.FAIL if findings else CheckStatus.PASS


def _check_default_policy(intent: Optional[Intent], config: dict[str, Any]) -> list[Finding]:
    if intent is None or not intent.default_action:
        return []
    actual = config.get("default_action")
    if actual in ALLOWED_ACTIONS and actual != intent.default_action:
        return [
            _finding(
                "DEFAULT_ACTION_MISMATCH",
                "MEDIUM",
                "intent",
                f"配置的默认策略与需求不一致：需求为 {intent.default_action}，配置为 {actual}。",
                f"default_action = {actual}，需求默认策略 = {intent.default_action}",
                "按需求调整默认策略，通常建议默认拒绝。",
                retryable=True,
            )
        ]
    return []


def _check_risk(intent: Optional[Intent], rules: list[dict[str, Any]], config: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    intent_src_any = bool(intent and intent.sources and parse_network(intent.sources[0])[0] == ANY_NET)

    for rule in rules:
        idx = rule.get("_index", 0) + 1
        if rule["action"] != "permit":
            continue
        src, dst = rule["_src"], rule["_dst"]
        src_any = src == ANY_NET
        dst_any = dst == ANY_NET

        if src_any and dst_any:
            findings.append(
                _finding(
                    "BROAD_PERMIT_ANY",
                    "CRITICAL",
                    "risk",
                    "命中预定义的宽泛放行规则：任意源到任意目标的 permit 规则。",
                    f"第 {idx} 条：permit {rule['protocol']} {src} -> {dst}",
                    "禁止自动通过，必须由人工确认；通常应改为最小授权范围。",
                    retryable=False,
                    blocking=True,
                )
            )
        elif src_any and not intent_src_any:
            findings.append(
                _finding(
                    "PERMIT_ANY_SOURCE",
                    "HIGH",
                    "risk",
                    f"放行规则使用了任意源地址（0.0.0.0/0），而需求只授权了特定源。",
                    f"第 {idx} 条：permit {rule['protocol']} {src} -> {dst}",
                    "将源地址收敛到需求授权范围。",
                    retryable=True,
                )
            )
        elif dst_any:
            findings.append(
                _finding(
                    "PERMIT_ANY_DESTINATION",
                    "HIGH",
                    "risk",
                    "放行规则的目标地址为任意地址（0.0.0.0/0）。",
                    f"第 {idx} 条：permit {rule['protocol']} {src} -> {dst}",
                    "将目标地址收敛到需求指定的服务器。",
                    retryable=True,
                )
            )

    if config.get("default_action") == "permit":
        findings.append(
            _finding(
                "DEFAULT_PERMIT",
                "HIGH",
                "risk",
                "默认策略为 permit：未被规则匹配的流量将被放行。",
                "default_action = permit",
                "改为默认拒绝（deny），仅按需放行。",
                retryable=True,
            )
        )

    return findings


def _build_checks(
    structure_findings: list[Finding],
    value_findings: list[Finding],
    intent_findings: list[Finding],
    intent_status: CheckStatus,
    risk_findings: list[Finding],
    structure_ok: bool,
) -> list[CheckResult]:
    checks: list[CheckResult] = []

    if structure_findings:
        status = CheckStatus.FAIL
    else:
        status = CheckStatus.PASS
    checks.append(
        CheckResult(
            key="A",
            name="JSON 结构与字段完整性",
            status=status.value,
            summary="配置可以解析，必要字段齐全。" if status == CheckStatus.PASS else "存在结构或字段问题。",
            findings=structure_findings,
        ).finalize()
    )

    if not structure_ok:
        value_status = CheckStatus.UNDETERMINED
        value_summary = "结构不合法，字段值检查无法可靠进行。"
    elif value_findings:
        value_status = CheckStatus.FAIL
        value_summary = "存在非法取值。"
    else:
        value_status = CheckStatus.PASS
        value_summary = "动作、协议、IP/CIDR、端口、默认策略取值合法。"
    checks.append(
        CheckResult(
            key="B",
            name="字段值合法性",
            status=value_status.value,
            summary=value_summary,
            findings=value_findings,
        ).finalize()
    )

    if intent_status == CheckStatus.UNDETERMINED or not structure_ok:
        intent_final = CheckStatus.UNDETERMINED
        intent_summary = "无法可靠地从需求中确定授权范围，需求符合度未能完整验证。"
    elif intent_findings:
        intent_final = CheckStatus.FAIL
        intent_summary = "生成配置与用户授权范围存在偏差。"
    else:
        intent_final = CheckStatus.PASS
        intent_summary = "源地址、目标地址、动作、协议与端口均在需求范围内。"
    checks.append(
        CheckResult(
            key="C",
            name="授权范围与需求符合度",
            status=intent_final.value,
            summary=intent_summary,
            findings=intent_findings,
        ).finalize()
    )

    if not structure_ok:
        risk_status = CheckStatus.UNDETERMINED
        risk_summary = "结构不合法，高风险规则检查无法完整执行。"
    elif risk_findings:
        risk_status = CheckStatus.FAIL
        risk_summary = "命中预定义高风险规则。"
    else:
        risk_status = CheckStatus.PASS
        risk_summary = "未命中当前已实现的预定义风险规则（不代表绝对安全）。"
    checks.append(
        CheckResult(
            key="D",
            name="预定义高风险规则",
            status=risk_status.value,
            summary=risk_summary,
            findings=risk_findings,
        ).finalize()
    )
    return checks


def validate_config(
    raw: Any,
    intent: Optional[Intent] = None,
    params: Optional[TaskParams] = None,
) -> ValidationReport:
    """对配置文本或字典执行完整校验。"""
    params = params or TaskParams()
    findings: list[Finding] = []

    if isinstance(raw, str):
        try:
            config = json.loads(raw)
        except json.JSONDecodeError as exc:
            report = ValidationReport(
                passed=False,
                status_suggestion=TaskStatus.FAILED.value,
                config_parsed=False,
                findings=[
                    _finding(
                        "JSON_PARSE_ERROR",
                        "CRITICAL",
                        "structure",
                        "配置文本不是合法 JSON，无法解析。",
                        f"解析错误：第 {exc.lineno} 行第 {exc.colno} 列，{exc.msg}",
                        "要求生成模块重新输出严格合法的 JSON。",
                        retryable=True,
                    )
                ],
                checks=[
                    CheckResult(
                        key="A",
                        name="JSON 结构与字段完整性",
                        status=CheckStatus.FAIL.value,
                        summary="JSON 解析失败。",
                        findings=[
                            _finding(
                                "JSON_PARSE_ERROR",
                                "CRITICAL",
                                "structure",
                                "配置文本不是合法 JSON。",
                                f"{exc.msg}（line {exc.lineno}）",
                                "重新生成合法的 JSON。",
                            )
                        ],
                    ).finalize(),
                    CheckResult(
                        key="B",
                        name="字段值合法性",
                        status=CheckStatus.UNDETERMINED.value,
                        summary="JSON 无法解析，跳过字段值检查。",
                    ).finalize(),
                    CheckResult(
                        key="C",
                        name="授权范围与需求符合度",
                        status=CheckStatus.UNDETERMINED.value,
                        summary="JSON 无法解析，无法比较授权范围。",
                    ).finalize(),
                    CheckResult(
                        key="D",
                        name="预定义高风险规则",
                        status=CheckStatus.UNDETERMINED.value,
                        summary="JSON 无法解析，无法执行风险规则检查。",
                    ).finalize(),
                ],
            )
            report.summary = _summary(report.findings)
            return report
    else:
        config = raw

    structure_findings, structure_ok, struct_rules = _check_structure(config)
    value_findings: list[Finding] = []
    checked_rules: list[dict[str, Any]] = []
    if isinstance(config, dict) and isinstance(config.get("rules"), list):
        value_findings, checked_rules = _check_values(config, struct_rules)

    intent_findings: list[Finding] = []
    intent_status = CheckStatus.UNDETERMINED
    risk_findings: list[Finding] = []
    if structure_ok and checked_rules:
        intent_findings, intent_status = _check_intent(intent, checked_rules)
        if intent is not None and intent.is_complete:
            intent_findings.extend(_check_default_policy(intent, config))
            if intent_findings:
                intent_status = CheckStatus.FAIL
        risk_findings = _check_risk(intent, checked_rules, config)

    findings = structure_findings + value_findings + intent_findings + risk_findings

    # 去重（同一 code + evidence）
    deduped: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for f in findings:
        key = (f.code, f.evidence)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    findings = deduped

    # 为“第 N 条规则”类问题补上规则下标，便于前端按规则展示风险状态
    rule_no_pattern = re.compile(r"第\s*(\d+)\s*条规则")
    for finding in findings:
        if finding.rule_index is None:
            matched = rule_no_pattern.search(finding.message)
            if matched:
                finding.rule_index = int(matched.group(1)) - 1

    checks = _build_checks(
        structure_findings, value_findings, intent_findings, intent_status, risk_findings, structure_ok
    )

    significant = [f for f in findings if f.severity in ("MEDIUM", "HIGH", "CRITICAL")]
    passed = not significant

    if any(f.blocking for f in findings):
        suggestion = TaskStatus.BLOCKED.value
    elif any(f.severity in ("HIGH", "CRITICAL") for f in findings):
        suggestion = TaskStatus.REVIEW_REQUIRED.value
    elif significant:
        suggestion = TaskStatus.REVIEW_REQUIRED.value
    elif findings:
        suggestion = TaskStatus.SUCCESS.value
    else:
        suggestion = TaskStatus.SUCCESS.value

    report = ValidationReport(
        passed=passed,
        status_suggestion=suggestion,
        findings=findings,
        checks=checks,
        rules_evaluated=len(checked_rules),
        config_parsed=True,
    )
    report.summary = _summary(findings)
    return report


def _summary(findings: list[Finding]) -> dict[str, int]:
    summary = {"INFO": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for f in findings:
        summary[f.severity] = summary.get(f.severity, 0) + 1
    return summary


def highest_severity(findings: list[Finding]) -> Optional[str]:
    if not findings:
        return None
    return max((f.severity for f in findings), key=lambda s: SEVERITY_ORDER[s])
