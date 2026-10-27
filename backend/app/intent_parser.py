"""演示模式的自然语言需求解析（确定性规则实现）。

说明：
- 这是**演示模式**下的“需求理解”实现，用正则与关键词匹配完成，不调用任何大模型；
- 解析结果会记录 missing / invalid_values / assumptions，信息不足时要求用户补充，
  不会“猜”具体 IP 地址；
- 在 API 模式下，同样的 Intent 结构由大模型填写（见 generator.py），
  但后续校验与流程控制逻辑完全一致。
"""

from __future__ import annotations

import ipaddress
import re

from .schemas import Intent

IP_CANDIDATE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?\b")
WIDEN_PATTERN = re.compile(r"覆盖\s*(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)")
PORT_PATTERN = re.compile(r"(?:端口|port)\s*[:：]?\s*(\d{1,5})", re.IGNORECASE)
PIVOT_PATTERN = re.compile(r"访问|访问到|连接到|到|至|→|->")

SERVICE_MAP: dict[str, tuple[str, int, str]] = {
    "https": ("tcp", 443, "HTTPS"),
    "http": ("tcp", 80, "HTTP"),
    "ssh": ("tcp", 22, "SSH"),
    "telnet": ("tcp", 23, "Telnet"),
    "ftp": ("tcp", 21, "FTP"),
    "smtp": ("tcp", 25, "SMTP"),
    "rdp": ("tcp", 3389, "RDP"),
    "远程桌面": ("tcp", 3389, "RDP"),
    "mysql": ("tcp", 3306, "MySQL"),
    "redis": ("tcp", 6379, "Redis"),
    "smb": ("tcp", 445, "SMB"),
    "ldap": ("tcp", 389, "LDAP"),
    "dns": ("udp", 53, "DNS"),
    "ntp": ("udp", 123, "NTP"),
    "snmp": ("udp", 161, "SNMP"),
    "ping": ("icmp", None, "ICMP Ping"),
}

FIELD_LABELS = {
    "source": "源地址",
    "destination": "目标地址",
    "action": "访问动作",
    "protocol": "协议 / 服务",
}


def _normalize_ip(token: str) -> tuple[str | None, str | None]:
    """返回 (规范化 CIDR, 错误原因)。"""
    try:
        if "/" in token:
            net = ipaddress.ip_network(token, strict=True)
        else:
            net = ipaddress.ip_network(f"{ipaddress.ip_address(token)}/{ipaddress.ip_address(token).max_prefixlen}")
    except ValueError as exc:
        return None, str(exc)
    return str(net), None


def _extract_default_action(text: str) -> tuple[str | None, str]:
    cleaned = text
    if re.search(r"默认\s*(?:拒绝|禁止|deny)", text, re.IGNORECASE):
        cleaned = re.sub(r"默认\s*(?:拒绝|禁止|deny)[^，。;；]*", " ", cleaned, flags=re.IGNORECASE)
        return "deny", cleaned
    if re.search(r"默认\s*(?:允许|放行|permit)", text, re.IGNORECASE):
        cleaned = re.sub(r"默认\s*(?:允许|放行|permit)[^，。;；]*", " ", cleaned, flags=re.IGNORECASE)
        return "permit", cleaned
    return None, cleaned


def parse_intent(text: str) -> Intent:
    intent = Intent(text=text, parse_mode="demo-rule")
    raw = text.strip()

    # ---- 1. 记录“显式扩大授权范围”的指令（原文要求，但会把配置带出授权范围）----
    for match in WIDEN_PATTERN.finditer(raw):
        token = match.group(1)
        normalized, err = _normalize_ip(token)
        if normalized is None:
            intent.invalid_values.append(f"扩大的网段“{token}”不是合法 CIDR：{err}")
            continue
        if intent.widen_source_hint is None:
            intent.widen_source_hint = normalized
        else:
            intent.widen_destination_hint = normalized
        intent.notes.append(
            f"用户原文要求生成“覆盖 {normalized}”的规则，该范围大于实际授权范围，"
            "生成器会按字面要求执行，校验模块将据此判定授权范围超出。"
        )

    # 去掉扩大指令片段，避免其网段被误当作授权源/目标地址
    cleaned = WIDEN_PATTERN.sub(" 覆盖[已记录] ", raw)

    # ---- 2. 默认策略 ----
    default_action, cleaned = _extract_default_action(cleaned)
    intent.default_action = default_action

    # ---- 3. 标记：演示用“模型持续扩大范围”场景 ----
    if "持续扩大" in raw or "持续放大" in raw:
        intent.stubborn_widen = True
        intent.notes.append("检测到演示标记：模拟生成模块在每次修正后仍扩大源地址范围。")

    # ---- 4. 宽泛放行识别 ----
    any_src = re.search(r"任意\s*(?:IPv4\s*)?源地址|任意\s*source|any\s+source", cleaned, re.IGNORECASE)
    any_dst = re.search(r"任意\s*(?:IPv4\s*)?(?:目标|目的)地址|任意\s*destination|any\s+destination", cleaned, re.IGNORECASE)
    if (any_src and any_dst) or re.search(r"\bany\s+any\b", cleaned, re.IGNORECASE):
        intent.any_any = True
        intent.sources = ["0.0.0.0/0"]
        intent.destinations = ["0.0.0.0/0"]
        intent.notes.append("需求本身要求任意源到任意目标的放行规则，属于宽泛放行场景。")

    # ---- 5. 动作 ----
    if re.search(r"拒绝|禁止|阻断|deny|block", cleaned, re.IGNORECASE):
        intent.action = "deny"
    elif re.search(r"允许|放行|permit|allow", cleaned, re.IGNORECASE):
        intent.action = "permit"

    # ---- 6. 服务 / 协议 / 端口 ----
    lowered = cleaned.lower()
    for keyword, (proto, port, label) in SERVICE_MAP.items():
        if keyword in lowered:
            intent.protocol = proto
            intent.destination_port = port
            intent.service_label = label
            break
    if intent.protocol is None:
        if re.search(r"\bTCP\b", cleaned, re.IGNORECASE):
            intent.protocol = "tcp"
        elif re.search(r"\bUDP\b", cleaned, re.IGNORECASE):
            intent.protocol = "udp"
        elif re.search(r"\bICMP\b", cleaned, re.IGNORECASE):
            intent.protocol = "icmp"
    port_match = PORT_PATTERN.search(cleaned)
    if port_match:
        try:
            intent.destination_port = int(port_match.group(1))
            intent.protocol = intent.protocol or "tcp"
        except ValueError:  # pragma: no cover - 正则已保证是数字
            pass
    if intent.protocol is None:
        intent.protocol = "ip"
        intent.assumptions.append("未指定协议与端口，按“ip 任意协议”处理，需人工确认是否合理。")

    # ---- 7. 地址抽取 ----
    if not intent.any_any:
        tokens = [(m.start(), m.group(0)) for m in IP_CANDIDATE.finditer(cleaned)]
        valid: list[tuple[int, str]] = []
        for pos, token in tokens:
            normalized, err = _normalize_ip(token)
            if normalized is None:
                intent.invalid_values.append(f"“{token}”不是合法 IP 地址或 CIDR：{err}")
            else:
                valid.append((pos, normalized))

        pivot = None
        for m in PIVOT_PATTERN.finditer(cleaned):
            if valid and m.start() > valid[0][0]:
                pivot = m.start()
                break

        if pivot is not None:
            src = [ip for pos, ip in valid if pos < pivot]
            dst = [ip for pos, ip in valid if pos > pivot]
        else:
            src = [ip for _, ip in valid[:1]]
            dst = [ip for _, ip in valid[1:2]]
            if len(valid) >= 2:
                intent.assumptions.append("未找到明确的“访问”连接词，按“第一个地址为源、第二个为目标”解析。")

        intent.sources = src
        intent.destinations = dst

    # ---- 8. 完整性判断 ----
    if not intent.sources:
        intent.missing.append("source")
    if not intent.destinations:
        intent.missing.append("destination")
    if intent.action is None:
        intent.missing.append("action")

    if intent.missing:
        missing_text = "、".join(FIELD_LABELS.get(m, m) for m in intent.missing)
        intent.notes.append(f"需求中缺少必要信息：{missing_text}，系统不会猜测具体地址。")
    if "办公网" in raw or "服务器" in raw:
        intent.notes.append("“办公网”“服务器”等表述不是可确定的具体网络地址，需要用户给出 IP 或 CIDR。")
    if intent.invalid_values:
        intent.notes.append("需求中包含无法解析的地址，已作为无效输入记录。")

    return intent
