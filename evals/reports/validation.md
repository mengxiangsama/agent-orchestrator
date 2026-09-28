# 验证报告

日期：2026-09-28。本机 macOS，Python 3.13.7。所有业务资料为隔离的合成夹具；没有真实支付、网络业务接口或部署。

## 结论与证据等级

本机 **81 个测试方法通过**：49 个状态检查器测试、6 个包检查测试、17 个报价实现测试、9 个主智能体独立报价测试。参数化子案例不额外计数。系统 skill-creator 的 quick_validate 也通过；它仅证明基础元数据格式。

以下行为不是从文档内容推断：本次真实使用宿主的 `multi_agent_v1` 创建、通信、等待和关闭能力。共创建 5 个独立执行者，最多同时保留 2 个；同一个报价执行者先做设计，再在主验收后接实现，最后接一次明确返工。平台并发上限未公开，2 是本轮选择，不是平台保证。

主智能体检查了实际文件、命令输出和本次子智能体工具调用记录，完成者均关闭释放。公开记录使用匿名负责人标签、相对交付路径，不发布包含本机路径的原始会话。原始 agent ID 和调用事件保留在该次宿主会话；公开摘要不冒充可独立认证的运行证明。

## 场景结果

| 要求 | 实际执行与观察 | 类型 / 结果 |
| --- | --- | --- |
| 简单任务不拆分 | 独立执行者读取 Skill 后，将带空白的 READY 转为 ready；检查其工具记录，没有再创建智能体或新聊天 | 独立前向测试；通过 |
| 两个独立任务并行 | V1 编写记录校验器，E1 编写示例；真实同时派发，写入集合不重叠；主智能体分别读文件、复测再接受 | 主智能体主导的真实编排集成演练；通过 |
| 设计验收后编码 | 独立设计请求先生成 D1；主智能体读完契约并核对原代码哈希后，才发 I1，提示词明确携带 D1 v1 和允许写入文件 | 真实通信与文件验证；通过 |
| 不合格后返工 | 首次候选原本通过16+9项测试；测试者随后把优惠上限改为商品额+运费，观察到反例20!=0/退出1；主智能体拒收，通过真实通信发第2次尝试；修复后17+9项通过 | 人为不合格交付注入 + 真实返工；通过，不声称自然模型缺陷 |
| 子任务失败 | `check_input.py` 被设计为报缺输入并退出7；执行者只运行一次，诊断固定失败，未创建依赖成功条件的 summary.md | 人为执行故障注入 + 真实处理；通过 |
| 缺少委派权限 | 明确禁止委派，但允许本地读写；执行者自己写中英文各3步，说明是授权限制而不是谎称宿主无工具；调用记录无委派 | 受限能力注入；通过，不等于在真正无工具宿主上验证 |
| 只设计不实现 | 第一轮请求只设计；仅新增 docs/design.md，原 src/payment.py 的SHA256不变；直到后续显式实现任务才改业务代码 | 独立前向测试；通过 |

独立前向测试只提供 Skill、原始用户风格请求和最小夹具，没有给出评分答案。编排集成和返工由主智能体主导，不将其包装成一次完全自主、无人介入的多智能体评测。

## 交付物与复测

- [轻量观察记录](observed-run.json)：从实际动作整理的状态摘要，使用匿名执行者标签与发布后的相对路径；事件顺序表达因果，不是逐条原始时间戳。F1 故意保留 failed，不能当成业务成功。
- [简单任务输入与输出](../artifacts/simple/request.json)、[实际输出](../artifacts/simple/output.txt)。
- [已验收报价设计](../artifacts/coupon/docs/design.md)、[最终实现](../artifacts/coupon/src/payment.py)、[执行者测试](../artifacts/coupon/tests/test_quote.py)、[主智能体独立 oracle](../artifacts/coupon/oracle/test_quote_contract.py)。这是完整支付示例的一个受限“报价计算”子场景，不声称完整订单/支付状态机已实现。
- [受限模式中文结果](../artifacts/restricted/zh.md)、[英文结果](../artifacts/restricted/en.md)、[故障注入检查器](../artifacts/restricted/check_input.py)。检查器应失败，不作为常规通过型测试运行。

在仓库根目录执行：

```bash
python3 scripts/validate_package.py
python3 -B -m unittest discover -s tests -v
python3 scripts/check_ledger.py examples/accepted-run.json
python3 scripts/check_ledger.py evals/reports/observed-run.json
```

报价夹具必须以 `evals/artifacts/coupon` 为工作目录执行（其测试从 `src` 导入；从仓库根目录直接收集曾得到导入错误，已修正 CI 工作目录）：

```bash
python3 -B -m unittest discover -s tests -v
python3 -B -m unittest discover -s oracle -v
```

上述本地命令最终均退出0。首个发布提交 `2bd7544` 的 [CI 运行](https://github.com/mengxiangsama/agent-orchestrator/actions/runs/36408800745) 已真实完成：Ubuntu/macOS/Windows + Python 3.12，以及 Ubuntu + Python 3.9，四个组合全部通过。后续提交的跨平台结果以各自的 [GitHub Actions](https://github.com/mengxiangsama/agent-orchestrator/actions) 为准，不把这次结果冒充所有未来提交的验证。

关键 SHA256（保留原字节的发布夹具）：

| 对象 | SHA256 |
| --- | --- |
| [设计前原代码](../artifacts/coupon/original-payment.py)，只设计后仍相同 | `3ca5779bb58d83375a74fed8d126a8869944fdb76b0e1d2062e57fa6aef22148` |
| D1 v1 设计，编码/返工后未变 | `b1b7552e0e9428ae9ed692b47228d766f971a8f51d3822ef0068a972e96432cb` |
| 最终报价实现 | `130025624059ab28750ed077b0ae691b4ef329854efd76f2465f8890306cfa84` |

## 仅确定性/文档检查的部分

设计变更后的取消、失效传播、新版本交接、陈旧版本拒绝、尝试预算耗尽、依赖循环、写入冲突、越权身份标签和并发上限，有正反例单元测试及文档示例；没有对每一项进行真实多进程竞态或真实运行中强制中断演练。

完整优惠券订单支付案例只做文档和链接检查。没有执行其中的真实支付、回调、并发争券、SQLite 事务故障或部署。

## 未验证与限制

- 没有物理移除子智能体工具的另一个宿主；本次只验证了明确禁用委派时的降级，以及真实执行失败。
- 未验证其他模型/客户端、超出本轮并发规模、远端隔离工作区传文件、进程重启恢复或生产项目。
- JSON 校验器是事后的一致性检查，不验证身份、证据真实性、真实文件系统隔离或业务授权；无法阻止宿主之外的并发写入。
- Skill 本身没有自动恢复服务、权限提升或后台执行能力。以上结果提高对这些具体场景的信心，不保证所有未来任务都正确。
