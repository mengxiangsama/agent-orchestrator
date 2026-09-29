# 分页编排演练：设计返工、执行失败与恢复

日期：2026-09-29。原始演练环境：macOS、Python 3.13.7、Python 标准库。

本次指定场景通过：D1 首次设计被拒绝、修订后主验收通过；之后才启动 I1；I1 首试遇到真实缺文件错误并停止，主智能体恢复输入后派发第 2 次；最终实现通过主智能体独立验收。未在本次可观察记录中发现提前启动依赖、超出尝试预算或主智能体代写实现的违规。

**这是预先知道故障位置的注入演练，不是盲测。** 公开材料是历史文件与命令结果的脱敏副本/摘要，不是可独立认证的原始工具调用轨迹。重新运行这些测试不会创建子智能体，也不能证明历史调度发生过。

## 来源与发布边界

- 当时使用真实 `collaboration.spawn_agent`、`followup_task`、`list_agents` 等宿主工具，不是模拟角色对话。原始工具调用留在该次会话，未把完整私有会话公开。
- 原演练写入独立临时目录；没有修改现有业务项目或 Skill，也没有联网、安装、提交或发布。**本次另获用户授权，只将脱敏测试材料整理到 GitHub**，不将发布过程算作原演练。
- 发布时逐文件核对：当时读取的已安装 `SKILL.md` 与四份 `references`，和源码提交 `efb13e1b8f64fa06dae60508fcee81f39f104075` 一致；本次不更改这些核心指令。
- `<TEMP_WORKSPACE>` 替换原临时目录；`<PYTHON_STDLIB>` 替换解释器安装路径；业务项目名替换成“现有项目”。命令、退出码、错误类别、事件顺序及观察时间保留。
- 两稿设计、分页实现、输入 fixture、17 项实现测试、20 项独立测试保留原字节。需求/证据/规则对应表有上述脱敏；本报告为公开版整理，非原报告逐字复制。
- `qa/check_evidence.py` 为发布适配版：失败 JSON 的哈希改为**脱敏副本**哈希，并显式使用 UTF-8。历史 `main-validation-3.json` 是原检查器当时的输出，不冒充发布适配版的运行输出。

## 实际执行者与尝试次数

工具返回的是以下 canonical task name，没有另行返回 UUID；这些 `/root/...` 字符串是任务标识，不是本机目录。

|任务|真实工具返回标识|状态路径|尝试次数|
|---|---|---|---|
|D1 设计|`/root/pagination_design_test`|首次 submitted → rework；第二次 submitted → accepted v1|2|
|I1 实现|`/root/pagination_implementation_test`|首次 failed；第二次 submitted → accepted v1|2|
|M1 整合|主智能体 `/root`|submitted → accepted v1|1|

最多同时运行 1 个子智能体，低于用户设定的 2；未递归派发。子智能体已完成本轮执行；该宿主没有暴露关闭/销毁工具，不能声称进程已销毁或资源已释放。

## 依赖启动与验收证据

以下为 2026-09-29 北京时间（UTC+8），是工具结果的观察/记录时刻，不是测量的子进程精确启动时刻。完整 UTC 序列见 [timeline.json](evidence/timeline.json)，任务状态与版本见 [run.json](run.json)。

|时刻|实际动作|可检查材料|
|---|---|---|
|09:32:39|创建 D1，尝试 1；未创建 I1|时间线事件 1|
|09:34:02|主智能体读完 50 行首稿，拒绝 R4 遗漏|[首稿](docs/design-attempt-1.md)、[拒绝记录](evidence/d1-rejection.md)|
|09:35:09|发出 D1 第 2 次尝试|时间线事件 4|
|09:37:56|读完 79 行修订稿，接受 D1 v1，先保存验收记录|[设计 v1](docs/design-v1.md)、[主验收](evidence/d1-acceptance-v1.md)|
|09:39:54|之后才创建 I1，明确传入 D1 v1 及 SHA256|时间线事件 7；两次 I1 start 均含 `inputs: {"D1": 1}`|
|09:40:34|I1 缺输入失败，确认停止；主智能体重放同样失败|[首试错误](evidence/i1-attempt-1.json)、[独立重放](evidence/main-missing-input-probe.json)|
|09:42:24|主智能体补输入并读成功后，才派发 I1 第 2 次|[恢复说明](evidence/i1-recovery.md)、[恢复读取](evidence/main-recovery-probe.json)|
|09:44:30|I1 提交实现和 17 项自测，尚未 accepted|[第二次提交](evidence/i1-attempt-2.json)|
|09:44:55|主智能体实读代码，独立重跑 17+20 项后接受 I1 v1|[I1 主验收](evidence/i1-acceptance-v1.md)|
|09:46:18|主智能体合并运行 37 项，退出 0|[合并输出](evidence/main-integration-tests.json)|
|09:48:46|完成并验收最终报告和规则对应表|时间线事件 13—14|

## 失败与返工，明确区分来源

1. **人为注入一：设计遗漏。** D1 首稿故意不写非法参数处理；主智能体读取实际文件后指出缺少 `ValueError("INVALID_ARGUMENT")` 及对应验证，拒绝并限定最后一次返工。没有在设计未通过时提前编码，也没有改写首稿来抹掉失败。
2. **人为注入二：执行缺文件。** I1 第一次项目操作运行下列真实命令，得到 `FileNotFoundError`、退出码 **1**。该次停止，仅写诊断，没有补猜输入、创建 fixture 或实现。主智能体独立重放失败，随后创建输入并验证退出 0；I1 第 2 次才开始实现。

```bash
python3 -B -c 'import json; from pathlib import Path; print(json.loads(Path("fixtures/records.json").read_text(encoding="utf-8")))'
```

3. **非注入的工具使用错误。** 主智能体曾在同一补丁中 Delete/Add `run.json`，被 `apply_patch` 拒绝。读取未变的文件后改用 Update File 保存记录。原错误见 [tooling-notes.md](evidence/tooling-notes.md)；这是主智能体的记录编辑错误，不是子任务第 3 次尝试，也不写成“全程没有错误”。

## 规则、实现与实际测试

[需求 R1—R6](requirements.md) → [设计条目 A1—A11 / E1—E11](docs/design-v1.md) → [分页实现](pagination.py) → [规则与测试结果对应表](traceability.md)。对应表逐条关联用户规则、设计、实现和具体测试方法。

|测试集|历史实际结果|源文件/日志|
|---|---|---|
|子智能体编写的实现测试|17 方法通过；主智能体也独立重跑，退出 0|[测试](tests/test_pagination.py)、[主复测输出](evidence/main-validation-1.json)|
|主智能体独立验收测试|20 方法通过，退出 0|[测试](qa/test_independent.py)、[输出](evidence/main-validation-2.json)|
|合并运行|37 方法通过，退出 0|[输出](evidence/main-integration-tests.json)|

37 = 17 + 20；多次重跑不重复计数。150 组固定种子输入属于其中 1 个独立测试方法的子案例，不额外记为 150 个测试方法。覆盖正常分页、乱序、空输入、越界、非法参数、输入不被修改、额外字段与稳定排序。

## 无网络复测（不调用模型）

要求 Python 3.9+，仅标准库。从仓库根目录开始：

```bash
python3 scripts/validate_package.py
python3 -B -m unittest discover -s tests -v
python3 scripts/check_ledger.py evals/artifacts/pagination/run.json
cd evals/artifacts/pagination
python3 -B qa/check_evidence.py
python3 -B -m unittest discover -s tests -v
python3 -B -m unittest discover -s qa -v
```

Windows 可将 `python3` 换成 `py -3`。CI 已配置运行这些检查，沿用 Ubuntu/macOS/Windows + Python 3.12、Ubuntu + Python 3.9 矩阵；是否通过以对应提交的 GitHub Actions 为准。跨平台 CI 只复测文件与 Python 行为，**不在 CI 重做真实智能体编排**。

发布整理时在本机重新实际运行：仓库测试 55 项、既有报价测试 17+9 项、新增分页测试 17+20 项，合计 **118 个测试方法通过**。包检查、三个状态记录检查、公开版证据检查也均退出 0。这是本次发布前复测，不新增历史子智能体尝试次数。

仓库元数据/链接检查与状态检查器不需要第三方库。发布整理时另外尝试了系统 `skill-creator` 的 `quick_validate.py`，当前解释器缺少可选 `yaml` 依赖，得到 `ModuleNotFoundError`，没有安装依赖；不把这项检查记为通过。

要重新做真实编排演练，使用[专门测试请求](../../pagination-prompt.md)，在新的独立临时目录让真实子智能体重新交付；不要直接复制这里的最终实现来伪装测试过程。

## 哈希与脱敏说明

|文件|SHA256|
|---|---|
|拒绝首稿（原字节）|`c564379488f5ce402cb8916c7d98a9863d7569813c4f7e4ae921964bc3be5a6d`|
|设计 v1（原字节）|`6a0fe8ec5b6edd62507486e73f3cf4941e809659e48e61ac700f9c8681647387`|
|分页实现（原字节）|`2ec28eed570138078965d8048c88a16eb3a956cff30da0dabd0062b03da02af2`|
|输入 fixture（原字节）|`ed5c433fce91e49fb48643f1d0bb8a86801ffc72c205d0f7106401a6456cec7b`|
|实现测试（原字节）|`b6116a41a3c01a582e49016e4be09d12ff86dfe6818f6c8b53530067778ff72d`|
|独立测试（原字节）|`e12d57f238cb209efd75095eb58e56f935d9e3c5c0006bd9bbc490aa9874f6b8`|
|失败 JSON（公开脱敏副本）|`1cb342e6d33351e9a78a4b64e3092613d94cee6957ff5e9cc0781852c47bc162`|

原失败 JSON 的哈希是 `776371ee6fb0d216d35f3c052b3758152d374e9d664252e4948f2ca82382a51f`，该未脱敏文件未发布。公开副本因路径替换而哈希不同，不能当成原字节证据。哈希和状态检查只能证明内部一致性，不能验证身份或真实工具调用。

## 未覆盖项目

- 不是隐藏故障的盲测，也不保证其他模型或未来任务能正确遵循规则。
- 未进行两个子智能体同时写入冲突、无工具宿主、容量耗尽、运行超时/中断、设计失效后的下游重验、多层依赖或跨会话恢复演练。
- 第 2 次实现成功，因此未在本演练测试“第 2 次再次失败后禁止第 3 次”的真实分支；状态检查器测试不能替代它。
- 原始真实编排只在 macOS / Python 3.13.7 执行。未对大数据性能、资源耗尽、恶意容器子类作保证。
- 没有进程级文件系统审计沙箱；范围结论依据可观察工具调用和文件记录，不宣称操作系统级隔离证明。
