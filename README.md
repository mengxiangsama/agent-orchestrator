# agent-orchestrator

[![Validate skill and records](https://github.com/mengxiangsama/agent-orchestrator/actions/workflows/validate.yml/badge.svg)](https://github.com/mengxiangsama/agent-orchestrator/actions/workflows/validate.yml)

适用于 Codex 的通用智能体编排 Skill：**你提出任务，主智能体判断是否拆分，按依赖调度，检查真实成果，再统一交付。**

Agent orchestration skill for scoped delegation, dependency-aware parallel work, acceptance gates, and bounded rework. Language- and domain-independent.

不是每次都创建三个角色，也不是“多开几个聊天”。简单任务直接完成；复杂任务按实际依赖和工具能力组织协作。

## 能做什么

- 区分分析、设计、实现、审查，保持用户原始范围。
- 生成自包含子任务提示词，不依赖隐含聊天历史。
- 独立任务并行；前置成果**主验收通过**后才启动依赖任务。
- 划分写入所有权，避免多个执行者同时修改同一文件。
- 区分执行者提交和主智能体验收，按具体问题有限返工。
- 前置设计改变后暂停、通知受影响任务并重新验收。
- 工具缺失时明确降级为单智能体，不假装已经派发。

**Skill 封装调度规则；执行、工具、模型、权限、隔离和并发限制来自运行环境。** 只安装 Skill 不会自动获得多智能体能力，也不保证所有客户端兼容。它不提供进程守护、任务队列、跨会话自动恢复或额外 API 额度。

## 安装

需要支持本地 `SKILL.md` 的宿主。以下使用 `~/.codex/skills` 举例；请确认你的客户端实际扫描目录，不要在多个扫描目录安装同名副本。

macOS / Linux：

```bash
git clone https://github.com/mengxiangsama/agent-orchestrator.git "$HOME/.codex/skills/agent-orchestrator"
```

Windows PowerShell（本项目安装不需要 Bash）：

```powershell
git clone https://github.com/mengxiangsama/agent-orchestrator.git "$env:USERPROFILE\.codex\skills\agent-orchestrator"
```

发现列表未更新时，刷新列表或新开会话；仍不显示再重启客户端。检查扫描目录下是否确实存在 `agent-orchestrator/SKILL.md`。WSL 与 Windows 的用户目录不同。

目录已存在时不要直接覆盖；检查是之前的安装还是自定义副本。本方式将仓库直接克隆到 Skill 目录，更新可执行：

```bash
git -C "$HOME/.codex/skills/agent-orchestrator" pull --ff-only
```

若只更新另一个源码目录，不会同步已复制的安装副本。有本地修改先审查并保留；不要使用强制重置来解决更新冲突。

## 调用

```text
使用 $agent-orchestrator 检查这个项目的订单导出模块，只报告问题，不改代码。
```

```text
使用 $agent-orchestrator 完善 CLI 参数解析及其使用文档，完成实现和测试。
需求明确时自动推进，只有影响业务结果的规则不明确时再问我。
```

```text
使用 $agent-orchestrator 设计优惠券订单支付模块，先只给设计，不写业务代码。
```

不要只用“你是设计师/程序员/测试员”来定义任务；分发提示词会包含输入、验收版本、读写范围、交付位置、验证要求和阻塞处理。

## 实际工作方式

1. 确认请求模式、关键规则和范围；简单任务由主智能体完成。
2. 有委派价值时核对真实工具，记录实际 agent ID 和本轮预算。
3. 建依赖和文件所有权；只派发前置已验收的任务。
4. 子智能体返回 `submitted`；主智能体打开交付物、核对证据。
5. 接受、返工或说明阻塞；必要集成检查后报告结果。

默认只有主智能体派发，每任务最多两次执行尝试；有具体新证据才调整预算。这个策略不意味着宿主固定支持两名子智能体。没有暴露并发上限时必须承认未知，不能编造平台参数。

## 项目内容

| 文件 | 用途 |
| --- | --- |
| [SKILL.md](SKILL.md) | 触发条件与核心调度流程 |
| [references/runtime.md](references/runtime.md) | 工具发现、能力限制与降级 |
| [references/dispatch.md](references/dispatch.md) | 自包含任务、成果返回、返工模板 |
| [references/ledger.md](references/ledger.md) | 轻量状态表和可选 JSON 记录契约 |
| [references/acceptance.md](references/acceptance.md) | 主验收和最终报告模板 |
| [examples/scenarios.md](examples/scenarios.md) | 简单、并行、失败、返工和设计模式示例 |
| [examples/coupon-order-payment.md](examples/coupon-order-payment.md) | 合成业务案例，不绑定具体语言 |
| [scripts/check_ledger.py](scripts/check_ledger.py) | 可选的记录一致性检查器，不是调度程序 |
| [evals/README.md](evals/README.md) | 行为评估方法、场景与证据边界 |
| [evals/reports/validation.md](evals/reports/validation.md) | 本次真实验证结果及未验证部分 |

## 验证

使用 Skill 的指令不依赖 Python。只有运行可选确定性检查器和仓库测试时需要 Python 3.9+，全部使用标准库：

```bash
python3 scripts/validate_package.py
python3 -B -m unittest discover -s tests -v
python3 scripts/check_ledger.py examples/accepted-run.json
```

Windows 将 `python3` 换为 `py -3`。CI 覆盖 Ubuntu、macOS、Windows 的 Python 3.12，并在 Ubuntu 上验证 Python 3.9。

验证分层：

- **包检查**：元数据、链接和资源是否完整；不证明模型行为。
- **确定性测试**：JSON 状态、依赖、版本、并发、所有权和预算是否一致；不证明实际工具调用或业务正确性。
- **真实行为评估**：在隔离的合成任务中观察真实子智能体调用、文件和命令结果；结果见验证报告。
- **受限/故障注入评估**：明确标注人为禁用能力、注入失败或不合格交付物，不包装成生产事故或自然出现的模型错误。

## 已知限制与安全

- 验收规则靠宿主执行；Skill 文字不是安全沙箱，也无法保证模型始终遵守。
- 不自动授予发布、部署、删除、付费、外部通信等权限；这些动作仍须在用户授权范围内。
- 文件所有权是协作约定，不能防住外部进程、符号链接或未协调的修改。
- 校验器只能验证输入记录，不核验真实身份、运行日志的真实性、业务规则或实际文件存在。
- 重启后必须重新核对真实状态，不保证自动恢复。
- 示例全部为合成资料。不要提交真实业务数据、凭证、私人路径或未授权代码。

欢迎通过 Issue 提供脱敏复现：请求、宿主能力、预期与实际行为、可公开的证据。修改调度规则时请补可观察的行为评估，而不只是检查某个句子是否出现在文档中。

[MIT License](LICENSE)
