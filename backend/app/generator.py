"""ACL 配置生成模块。

两种实现共用 `generate()` 接口，Agent 不关心配置来自哪里：

- DemoGenerator：**演示模式**。用确定性规则把解析出的需求组装成 ACL JSON，
  并对“用户原文要求扩大范围”“模型持续扩大范围”等演示场景做可控模拟。
  它不调用任何大模型，界面与接口都会明确标注为演示数据。
- LLMGenerator：**API 模式**。通过后端调用真实模型服务并获得 JSON 文本，
  然后做结构化解析；解析失败会作为可修正错误交给 Agent 处理。

注意：生成器的输出永远只是“候选配置”，必须经过 validator 独立校验。
"""

from __future__ import annotations

import ipaddress
import json
import re
from typing import Any, Optional

from .intent_parser import parse_intent
from .llm_client import LLMError, OpenAICompatibleClient
from .schemas import GenerationResult, Intent, TaskParams

SYSTEM_PROMPT = """你是一个网络 ACL 配置生成助手。只能输出一个 JSON 对象，不要输出解释、不要使用 Markdown 代码块。
JSON 结构必须严格如下：
{
  "rules": [
    {
      "action": "permit" | "deny",
      "protocol": "tcp" | "udp" | "icmp" | "ip",
      "source": "IPv4 地址或 CIDR",
      "destination": "IPv4 地址或 CIDR",
      "destination_port": 整数或 null
    }
  ],
  "default_action": "permit" | "deny"
}
要求：
1. 不得擅自把源地址或目标地址扩大到用户未授权的网段；
2. 不得使用 0.0.0.0/0 作为源或目标，除非用户明确要求任意地址；
3. 服务端口按需求确定，HTTPS=443/tcp、SSH=22/tcp、HTTP=80/tcp、DNS=53/udp；
4. 默认策略在用户未说明时使用 deny；
5. 如果需求缺少必要的源地址或目标地址，输出 {"error":"NEED_INFO","missing":["source"]}，不要猜测地址。"""


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    return fence.group(1) if fence else cleaned


def _widen(net: ipaddress._BaseNetwork, prefix: int = 24) -> str:
    """把网络扩大到指定前缀（例如 /32 → /24），仅用于演示“模型把范围写大”。"""
    if net.version != 4 or prefix >= net.prefixlen:
        return str(net)
    return str(ipaddress.ip_network(f"{net.network_address}/{prefix}", strict=False))


class DemoGenerator:
    """演示模式生成器（确定性、可重复、可解释）。"""

    source = "demo"

    def generate(
        self,
        intent: Intent,
        attempt_index: int = 0,
        feedback_codes: Optional[list[str]] = None,
        params: Optional[TaskParams] = None,
    ) -> GenerationResult:
        feedback_codes = feedback_codes or []
        is_correction = attempt_index > 0 and bool(feedback_codes)
        notes: list[str] = []

        src = intent.sources[0] if intent.sources else "0.0.0.0/0"
        dst = intent.destinations[0] if intent.destinations else "0.0.0.0/0"

        # 1) 用户原文明确要求“生成覆盖更大网段”的规则 —— 按字面执行，形成可被校验捕获的偏差
        if intent.widen_source_hint:
            if is_correction and not intent.stubborn_widen:
                notes.append(
                    f"根据校验反馈，把源地址从 {intent.widen_source_hint} 收敛回授权范围 {src}。"
                )
            else:
                src = intent.widen_source_hint
                notes.append(
                    f"按用户原文“覆盖 {intent.widen_source_hint}”的指令生成源地址，"
                    f"该范围大于实际授权范围 {intent.sources[0] if intent.sources else '-'}。"
                )
        elif intent.stubborn_widen and intent.sources:
            src = _widen(ipaddress.ip_network(intent.sources[0], strict=False), 24)
            notes.append(
                f"演示场景：模拟生成模块未按反馈修正，仍把源地址扩大到 {src}。"
            )

        # 2) 目标地址扩大
        if intent.widen_destination_hint:
            if is_correction and not intent.stubborn_widen:
                notes.append(
                    f"根据校验反馈，把目标地址从 {intent.widen_destination_hint} 收敛回 {dst}。"
                )
            else:
                dst = intent.widen_destination_hint
                notes.append(
                    f"按用户原文“覆盖 {intent.widen_destination_hint}”的指令生成目标地址。"
                )

        protocol = intent.protocol or "ip"
        port = intent.destination_port if protocol in ("tcp", "udp") else None
        action = intent.action or "permit"
        default_action = intent.default_action or "deny"
        if intent.default_action is None:
            notes.append("需求未明示默认策略，按最小权限假设取 default_action = deny。")

        rule: dict[str, Any] = {
            "action": action,
            "protocol": protocol,
            "source": src,
            "destination": dst,
        }
        if port is not None:
            rule["destination_port"] = port
        rule["description"] = "演示模式生成的候选规则（仅用于原型验证）"

        config = {"rules": [rule], "default_action": default_action}
        raw = json.dumps(config, ensure_ascii=False, indent=2)
        if not notes:
            notes.append("根据解析出的源地址、目标地址、协议与服务端口生成单条规则。")
        return GenerationResult(
            raw=raw,
            config=config,
            note=" ".join(notes),
            source="demo",
            latency_ms=0,
        )


class FixedConfigGenerator:
    """测试用例专用：返回预先给定的待检查配置，检验校验模块的行为。"""

    source = "fixed"

    def __init__(self, payload: Optional[dict[str, Any]], note: str = "") -> None:
        self.payload = payload
        self.note = note or "使用测试用例预先构造的配置，用于检验校验模块（不可由生成器修正）。"

    def generate(
        self,
        intent: Intent,
        attempt_index: int = 0,
        feedback_codes: Optional[list[str]] = None,
        params: Optional[TaskParams] = None,
    ) -> GenerationResult:
        if self.payload is None:
            return GenerationResult(
                raw="",
                config=None,
                note=self.note,
                source="fixed",
                error="测试用例未提供配置",
            )
        raw = json.dumps(self.payload, ensure_ascii=False, indent=2)
        return GenerationResult(raw=raw, config=json.loads(raw), note=self.note, source="fixed")


class LLMGenerator:
    """API 模式生成器：调用真实模型服务生成配置。"""

    source = "llm"

    def __init__(self, client: Optional[OpenAICompatibleClient] = None) -> None:
        self.client = client or OpenAICompatibleClient()

    async def generate(
        self,
        intent: Intent,
        attempt_index: int = 0,
        feedback_codes: Optional[list[str]] = None,
        params: Optional[TaskParams] = None,
        feedback_detail: Optional[list[str]] = None,
    ) -> GenerationResult:
        constraint_lines = [
            f"用户原始需求：{intent.text}",
            f"确定性解析得到的授权基线：源 {intent.sources or '未知'}，目标 {intent.destinations or '未知'}，"
            f"动作 {intent.action or '未知'}，协议 {intent.protocol or '未知'}，"
            f"端口 {intent.destination_port if intent.destination_port is not None else '未指定'}。",
            "生成配置不得超出上述授权基线。",
        ]
        if feedback_detail:
            constraint_lines.append("上一轮校验未通过，必须修正以下问题：")
            constraint_lines.extend(f"- {item}" for item in feedback_detail)

        try:
            response = await self.client.chat(SYSTEM_PROMPT, "\n".join(constraint_lines))
        except LLMError as exc:
            return GenerationResult(
                raw="", config=None, note=f"模型调用失败：{exc}", source="llm", error=str(exc)
            )

        text = _strip_code_fence(response.text)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return GenerationResult(
                raw=response.text,
                config=None,
                note=f"模型返回的内容不是合法 JSON（{exc.msg}）。",
                source="llm",
                model=response.model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                latency_ms=response.latency_ms,
                error="MODEL_JSON_INVALID",
            )

        if isinstance(parsed, dict) and parsed.get("error") == "NEED_INFO":
            missing = parsed.get("missing") or []
            return GenerationResult(
                raw=response.text,
                config=None,
                note=f"模型认为需求信息不足，缺少：{', '.join(map(str, missing))}",
                source="llm",
                model=response.model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                latency_ms=response.latency_ms,
                error="NEED_INFO",
            )

        note = "真实模型返回结构化配置。"
        if attempt_index > 0:
            note = f"第 {attempt_index} 次修正后由真实模型重新生成配置。"
        return GenerationResult(
            raw=response.text,
            config=parsed if isinstance(parsed, dict) else None,
            note=note,
            source="llm",
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_ms=response.latency_ms,
        )


def build_generator(params: TaskParams):
    if params.mode == "api":
        return LLMGenerator()
    return DemoGenerator()
