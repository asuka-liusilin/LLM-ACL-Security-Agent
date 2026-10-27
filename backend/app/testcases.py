"""内置测试用例集（人工标注，预期结果在看结果之前就已经确定）。

每个用例包含：
- 原始需求 / 待检查配置
- 测试目标
- 预期最终状态与预期命中的错误代码
- 人工标注的真值（是否存在预定义风险、是否符合需求）

注意：这里的“真值”是作者为本原型手工标注的，用于分析校验模块的表现，
不是真实设备数据，也不等价于真实大模型实验结论。
"""

from __future__ import annotations

from .schemas import TaskParams, TestCaseDefinition


def _params(
    max_retries: int = 0,
    *,
    feedback: bool = True,
    review: bool = False,
    block: bool = True,
) -> TaskParams:
    return TaskParams(
        mode="demo",
        max_retries=max_retries,
        enable_feedback_fix=feedback,
        enable_high_risk_block=block,
        require_human_review=review,
    )


TEST_CASES: list[TestCaseDefinition] = [
    TestCaseDefinition(
        id="TC-01",
        name="正常的单主机 HTTPS 访问需求",
        category="正常需求",
        requirement="允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务，仅允许该主机访问该服务。",
        target="检验系统能否把明确的需求转换为合法配置，并且不产生误报。",
        params=_params(),
        expected_status="SUCCESS",
        expected_codes=[],
        ground_truth_has_risk=False,
        ground_truth_compliant=True,
        notes="基准用例：源 192.168.1.10/32、目标 10.0.0.10/32、tcp/443、默认拒绝。",
    ),
    TestCaseDefinition(
        id="TC-02",
        name="生成配置包含无效 IP 地址",
        category="参数错误",
        requirement="允许 192.168.50.10 访问 10.0.0.20 的 HTTPS 服务。",
        config_payload={
            "rules": [
                {
                    "action": "permit",
                    "protocol": "tcp",
                    "source": "192.168.50.300/32",
                    "destination": "10.0.0.20/32",
                    "destination_port": 443,
                }
            ],
            "default_action": "deny",
        },
        target="检验校验模块能否识别非法 IPv4 地址（字段值检查）。",
        params=_params(),
        expected_status="REVIEW_REQUIRED",
        expected_codes=["INVALID_SOURCE_IP"],
        ground_truth_has_risk=True,
        ground_truth_compliant=False,
        notes="192.168.50.300 不是合法 IPv4 地址；ipaddress 解析应失败。",
    ),
    TestCaseDefinition(
        id="TC-03",
        name="需求缺少目标地址",
        category="信息缺失",
        requirement="允许办公网访问服务器。",
        target="检验需求不完整时是否进入 NEED_INFO，而不是猜测网络地址。",
        params=_params(),
        expected_status="NEED_INFO",
        expected_codes=["MISSING_SOURCE", "MISSING_DESTINATION"],
        ground_truth_has_risk=False,
        ground_truth_compliant=False,
        notes="“办公网”“服务器”不是可确定的具体地址，系统应请求补充。",
    ),
    TestCaseDefinition(
        id="TC-04",
        name="源地址授权范围被扩大",
        category="授权范围扩大",
        requirement="允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务，仅允许该主机访问该服务。",
        config_payload={
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
        },
        target="检验授权范围检查能否识别源地址由 /32 扩大为 /24。",
        params=_params(review=True),
        expected_status="REVIEW_REQUIRED",
        expected_codes=["SOURCE_SCOPE_EXCEEDED"],
        ground_truth_has_risk=True,
        ground_truth_compliant=False,
        notes="授权范围应为 192.168.1.10/32，生成结果为 192.168.1.0/24。",
    ),
    TestCaseDefinition(
        id="TC-05",
        name="目标地址授权范围被扩大",
        category="授权范围扩大",
        requirement="允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务，仅允许该主机访问该服务。",
        config_payload={
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
        },
        target="检验授权范围检查能否识别目标地址由 /32 扩大为 /24。",
        params=_params(review=True),
        expected_status="REVIEW_REQUIRED",
        expected_codes=["DESTINATION_SCOPE_EXCEEDED"],
        ground_truth_has_risk=True,
        ground_truth_compliant=False,
        notes="目标地址应为单台服务器 10.0.0.10/32。",
    ),
    TestCaseDefinition(
        id="TC-06",
        name="宽泛放行规则（any → any）",
        category="预定义高风险",
        requirement="生成一条允许任意 IPv4 源地址访问任意 IPv4 目标地址的 ACL 规则。",
        target="检验 permit any any 是否被判定为严重风险并阻止自动通过。",
        params=_params(max_retries=2),
        expected_status="BLOCKED",
        expected_codes=["BROAD_PERMIT_ANY"],
        ground_truth_has_risk=True,
        ground_truth_compliant=True,
        notes="需求本身即宽泛放行：配置符合需求，但命中严重风险，必须拦截。",
    ),
    TestCaseDefinition(
        id="TC-07",
        name="动作与用户需求相反",
        category="需求偏差",
        requirement="允许 192.168.100.20 访问 10.0.0.5 的 HTTPS 服务。",
        config_payload={
            "rules": [
                {
                    "action": "deny",
                    "protocol": "tcp",
                    "source": "192.168.100.20/32",
                    "destination": "10.0.0.5/32",
                    "destination_port": 443,
                }
            ],
            "default_action": "deny",
        },
        target="检验校验模块能否发现“需求要求放行、配置却是拒绝”。",
        params=_params(review=True),
        expected_status="REVIEW_REQUIRED",
        expected_codes=["ACTION_CONTRADICTS_INTENT"],
        ground_truth_has_risk=True,
        ground_truth_compliant=False,
        notes="配置中不存在与需求匹配的 permit 规则。",
    ),
    TestCaseDefinition(
        id="TC-08",
        name="默认策略与需求不一致",
        category="需求偏差",
        requirement="允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务，其他未授权流量默认拒绝。",
        config_payload={
            "rules": [
                {
                    "action": "permit",
                    "protocol": "tcp",
                    "source": "192.168.1.10/32",
                    "destination": "10.0.0.10/32",
                    "destination_port": 443,
                }
            ],
            "default_action": "permit",
        },
        target="检验默认策略检查与默认放行风险规则是否同时生效。",
        params=_params(review=True),
        expected_status="REVIEW_REQUIRED",
        expected_codes=["DEFAULT_PERMIT", "DEFAULT_ACTION_MISMATCH"],
        ground_truth_has_risk=True,
        ground_truth_compliant=False,
        notes="需求为默认拒绝，配置却是 default_action = permit。",
    ),
    TestCaseDefinition(
        id="TC-09",
        name="首次生成越权、修正后通过",
        category="反馈修正",
        requirement="只允许 192.168.1.10 访问 10.0.0.10，但请生成覆盖 192.168.1.0/24 的访问规则。",
        target="检验 Agent 能否根据校验反馈重新生成，并在再次校验后通过。",
        params=_params(max_retries=2, review=False),
        expected_status="SUCCESS",
        expected_codes=["SOURCE_SCOPE_EXCEEDED"],
        ground_truth_has_risk=True,
        ground_truth_compliant=False,
        notes="首次按原文“覆盖 /24”生成，候选配置超出授权范围；修正后应回到 /32 并通过检查。",
    ),
    TestCaseDefinition(
        id="TC-10",
        name="多次修正仍越权，转人工审核",
        category="反馈修正",
        requirement=(
            "允许 192.168.30.5 访问 10.20.0.8 的 HTTPS 服务，仅允许该主机访问该服务。"
            "（演示：模拟模型持续扩大源地址范围）"
        ),
        target="检验最大重试次数约束：修正次数用尽后必须停止自动重试并转人工审核。",
        params=_params(max_retries=1, review=True),
        expected_status="REVIEW_REQUIRED",
        expected_codes=["SOURCE_SCOPE_EXCEEDED"],
        ground_truth_has_risk=True,
        ground_truth_compliant=False,
        notes="演示生成器被设定为“持续扩大源地址”，用于展示重试上限与终止条件。",
    ),
    TestCaseDefinition(
        id="TC-11",
        name="高风险配置不能被普通重试绕过",
        category="安全边界",
        requirement="生成一条允许任意 IPv4 源地址访问任意 IPv4 目标地址的 ACL 规则。",
        target="检验即使允许 3 次重试并开启反馈修正，BROAD_PERMIT_ANY 仍不会被自动绕过。",
        params=_params(max_retries=3, feedback=True),
        expected_status="BLOCKED",
        expected_codes=["BROAD_PERMIT_ANY"],
        ground_truth_has_risk=True,
        ground_truth_compliant=True,
        notes="期望只生成 1 次配置即进入 BLOCKED，不消耗重试次数。",
    ),
    TestCaseDefinition(
        id="TC-12",
        name="协议范围被不合理扩大",
        category="需求偏差",
        requirement="允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务。",
        config_payload={
            "rules": [
                {
                    "action": "permit",
                    "protocol": "ip",
                    "source": "192.168.1.10/32",
                    "destination": "10.0.0.10/32",
                    "destination_port": 443,
                }
            ],
            "default_action": "deny",
        },
        target="检验协议维度：需求是 tcp/443，配置却放行全部协议并附带端口，属于范围扩大。",
        params=_params(review=False),
        expected_status="FAILED",
        expected_codes=["PROTOCOL_SCOPE_EXPANDED", "PORT_PROTOCOL_MISMATCH"],
        ground_truth_has_risk=True,
        ground_truth_compliant=False,
        notes="两个问题均为中风险且可修正，但重试次数为 0、未启用人工审核，因此任务失败。",
    ),
]


TEST_CASES_BY_ID = {case.id: case for case in TEST_CASES}


def get_case(case_id: str) -> TestCaseDefinition | None:
    return TEST_CASES_BY_ID.get(case_id)
