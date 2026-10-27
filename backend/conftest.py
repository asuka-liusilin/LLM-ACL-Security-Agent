"""pytest 公共配置：确保测试不依赖真实模型服务、也不依赖演示动画延迟。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 必须在导入 app 之前设置：关闭步骤延迟，并保证没有配置真实 API Key
os.environ["AGENT_STEP_DELAY"] = "0"
os.environ.pop("LLM_API_KEY", None)
os.environ["LLM_API_KEY"] = ""


def pytest_configure(config):  # pragma: no cover - pytest 钩子
    config.addinivalue_line("markers", "anyio: 预留标记")
