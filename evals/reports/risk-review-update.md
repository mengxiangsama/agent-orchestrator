# 2026-09-29 审查规则更新验证

本轮更新风险分级、独立审查材料、修复后的定向复查及最终集成要求。没有修改调度脚本、记录格式或业务实现；保留契约优先并行、滚动验收、主智能体控制和原有尝试预算。

## 实际执行的本地检查

环境：macOS，Python 3.13.7。以下命令实际执行并成功退出；计数按测试方法，不把参数子用例另计。

| 工作目录（相对仓库根目录） | 命令 | 结果 |
| --- | --- | --- |
| `.` | `python3 -B scripts/validate_package.py` | 元数据、必需资源与本地链接通过 |
| `.` | `python3 -B -m unittest discover -s tests -q` | 63 项通过 |
| `evals/artifacts/coupon` | `python3 -B -m unittest discover -s tests -q` | 17 项通过 |
| `evals/artifacts/coupon` | `python3 -B -m unittest discover -s oracle -q` | 9 项通过 |
| `evals/artifacts/pagination` | `python3 -B -m unittest discover -s tests -q` | 17 项通过 |
| `evals/artifacts/pagination` | `python3 -B -m unittest discover -s qa -q` | 20 项通过 |
| `evals/artifacts/pagination` | `python3 -B qa/check_evidence.py` | 既有事件顺序、尝试次数与证据哈希检查通过 |
| `.` | `git diff --check` | 通过 |

共 126 项既有测试通过，另对 `examples/accepted-run.json`、`evals/reports/observed-run.json`、`evals/artifacts/pagination/run.json` 实际运行了 `scripts/check_ledger.py`，均通过。这些检查证明现有记录、包和合成夹具没有检测到回归，不证明新增指令在所有模型中都会正确执行。

通用 Skill 快速校验器在系统 Python 和已有内置 Python 环境中均因缺少 `yaml`（PyYAML）无法启动；未为此安装新依赖。仓库自带、仅用标准库的包校验器成功执行。两者结果不能混称为“所有校验器通过”。

## 独立审查与场景推演

本轮实际创建一名未参与编写的只读子智能体 R1，给出原始需求、9 个候选文件、Git 基线、变更范围与已有验证结果。R1 读取真实内容及差异、记录前后文件哈希、实际执行包检查与差异检查，未发现可证实的阻塞问题。主智能体核对报告、实际差异及候选哈希后接受这份审查结果，并调用宿主关闭工具释放审查者。

审查候选基线为 `6effb4c14a60d2fd9ee4e9b3c2d4d163c33970ca`；核心规则 `SKILL.md` 的 SHA-256 为 `29acd2dbf7363c31b8b1e53decec104216254bc8c3c69b1675f39b5751986965`，`references/review.md` 为 `8a2a1a26aa06bfe67b0bb1c9a1edad646f75a2f0995a90cfe4c34dfbcabe9b12`。审查前后 9 个候选均未变化。本报告随后补充，由主智能体核对，不属于 R1 的审查范围。

R1 另对以下五种合成输入作了文档场景推演，主智能体核对其决策与规则一致：

| 输入 | 推演结果 |
| --- | --- |
| 仅改 CLI 帮助文本拼写 | 主智能体核对差异与帮助输出，不固定创建审查者 |
| 修改优惠券金额边界，文档任务并行 | 金额候选保持 submitted，安排非实现者审查；无关文档照常推进并独立验收 |
| S1 已审查，修复 S2 改共享返回字段 | 旧结论不覆盖新候选；协调契约与受影响任务，扩大复查，预算不重置 |
| 高风险需审查，但宿主没有子智能体 | 披露独立审查缺口，自查不冒充独立通过，禁止提前放行下游 |
| 用户只要求审查支付模块 | 只交问题与证据，不修改业务代码、不安排未授权实现 |

这些是模型对文档的解释与推演，不是五次真实业务执行，也不是盲测。R1 没有重新执行或独立核验全部 126 项测试的原始日志；这些实测证据由主智能体取得。本轮没有发现需返工的问题，所以没有实际运行一轮“修复后重新派发独立审查”的闭环。

## 验证边界

- 这次没有新增仅匹配文案的测试，也没有修改 JSON v1 来伪装强制审查关卡；审查身份、风险选择及证据真实性仍需主智能体核对。
- 既有订单/优惠券与分页夹具是合成测试，不是生产支付或线上集成验证。
- 本轮本地命令未覆盖 Windows、Linux 或远程 CI；旧 CI 状态不能证明本轮改动已在这些平台通过。
- 未执行发布、部署或 GitHub 推送。
