"""可替换的模型客户端接口。

当前实现为 OpenAI 兼容的 /chat/completions 协议（DeepSeek、通义、Moonshot、
OpenAI 等多数服务均兼容）。如需更换服务商，只要实现 `ModelClient.chat`
即可，Agent 与校验模块不需要修改。

安全约定：
- API Key 只从后端环境变量读取；
- 任何异常都会转换成中文错误信息，不包含 Key；
- 只返回文本，不执行模型输出中的任何内容。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from .config import settings


class LLMError(Exception):
    """模型调用失败（超时、HTTP 错误、返回为空等）。"""


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int = 0


class ModelClient(Protocol):
    async def chat(self, system: str, user: str) -> LLMResponse:  # pragma: no cover - 协议定义
        ...


class OpenAICompatibleClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self.timeout = timeout or settings.llm_timeout

    async def chat(self, system: str, user: str) -> LLMResponse:
        if not self.api_key:
            raise LLMError("未配置 LLM_API_KEY，无法调用真实模型服务。请在 .env 中配置或改用演示模式。")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise LLMError(f"模型服务响应超时（>{self.timeout:.0f}s），请稍后重试或改用演示模式。") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"无法连接模型服务：{type(exc).__name__}。请检查 LLM_BASE_URL 与网络。") from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code != 200:
            detail = resp.text[:200].replace(self.api_key, "***")
            raise LLMError(f"模型服务返回 HTTP {resp.status_code}：{detail}")

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError) as exc:
            raise LLMError("模型服务返回的数据结构不符合预期（缺少 choices/message/content）。") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("模型返回内容为空。")

        usage = data.get("usage") or {}
        return LLMResponse(
            text=content,
            model=str(data.get("model") or self.model),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_ms=latency_ms,
        )


def build_client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient()
