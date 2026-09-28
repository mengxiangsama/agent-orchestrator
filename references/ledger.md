# 轻量任务记录与依赖版本

默认用短表格或笔记；长任务可以保存到用户允许的位置。记录文件不是恢复引擎，不要为一句话任务强制生成一套表格。

| ID | 负责人/实际 agent ID | 前置与版本 | 可写范围 | 状态 | 交付物 | 主智能体验收 |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | 主智能体或工具返回 ID | 无 | docs/payment.md | accepted | 设计 v1 | 规则和接口已逐项检查 |
| I1 | 工具返回 ID | D1 v1 | src/payment/ | running | 预定：实现与测试 | 待验收 |

状态：`pending → running → submitted → accepted`。不合格 `submitted → rework → running`；异常为 `failed / blocked / cancelled`。前置变更导致 `invalidated`；重新执行并验收后才能恢复为 `accepted`。

依赖不是“文件出现就能开始”：前置必须 accepted，执行者须明确收到对应版本。作废前置前先停止受影响的 running/submitted 任务；对子孙任务清除旧验收，通知变更并重验。仅静态相同的文件路径不能证明版本一致。

## 可选 JSON 检查格式（schema_version 1）

需要检查依赖图、状态转移、并发和写入冲突时，可用 `python3 scripts/check_ledger.py run.json`。该脚本**只验证记录内部一致性**，不调用工具、不执行任务、不读取交付物，不证明日志/agent ID真实，不验证业务语义，也不自动恢复。

根字段：

- `schema_version`: 1。
- `mode`: `analyze | design | implement | review`，只记录用户模式；脚本不凭后缀推断业务授权。
- `limits`: `max_active`、`max_attempts`，均为正整数。这是本轮选定预算，不冒充平台真实限额。
- `tasks`: 每项含唯一 `id`、非空 `owner`、`depends_on`（任务 ID 列表）、`write_paths`（无通配符的相对文件/目录）、`deliverables`（非空字符串列表）、`acceptance`（非空字符串列表）。可选 `status` 必须等于事件推导的最终状态。
- `events`: 有序事件列表，每项含 `task`、`event`、`actor`；可选 `reason`、`evidence`（非空字符串列表）、`inputs`（依赖 ID→验收版本整数）、`revision`。

事件语义（顺序即记录顺序，不宣称精确壁钟时间）：

| event | 条件 / 效果 |
| --- | --- |
| `start` | 仅 main；从 pending/rework/failed/blocked/cancelled/invalidated 到 running；重试必须 reason；尝试数+1，不超预算；所有依赖 accepted，inputs 精确等于依赖当前版本；占一个 active 槽 |
| `submit` | owner 或 main；running→submitted；必须 evidence；仍保留写入所有权至主智能体验收/退回/停止确认 |
| `accept` | 仅 main；submitted→accepted；必须 evidence；revision 从 1 严格递增；释放槽 |
| `reject` | 仅 main；submitted→rework；必须 reason；释放槽 |
| `fail` / `block` | owner 或 main；running/submitted→failed/blocked；必须 reason；表示主智能体已确认该次尝试停止，释放槽 |
| `cancel` | 仅 main；running/submitted→cancelled；必须 reason；仅在真实停止确认后记录，释放槽 |
| `invalidate` | 仅 main；accepted→invalidated；必须 reason；不允许仍有 running/submitted 子孙；已执行子孙同步 invalidated，pending 子孙保持 pending，旧验收版本失效 |

`main` 是主智能体身份标签，其他 owner 是稳定的负责人/实际工具 ID 标签。脚本不验证身份凭证。互不依赖且写入范围无冲突的任务可并行；同一路径或父子目录冲突。`write_paths: []` 表示只读；`.` 表示整个工作区。路径按可移植格式保守比较（忽略大小写）；不支持 `..`、绝对路径、反斜杠或 glob，不替代真实文件系统的符号链接/挂载隔离。

最小单任务记录：

```json
{
  "schema_version": 1,
  "mode": "analyze",
  "limits": {"max_active": 1, "max_attempts": 2},
  "tasks": [{"id": "A1", "owner": "main", "depends_on": [], "write_paths": [],
    "deliverables": ["回复中的结论"], "acceptance": ["回答用户问题且不改代码"]}],
  "events": [
    {"task": "A1", "event": "start", "actor": "main", "inputs": {}},
    {"task": "A1", "event": "submit", "actor": "main", "evidence": ["完成分析回复"]},
    {"task": "A1", "event": "accept", "actor": "main", "revision": 1, "evidence": ["逐项核对请求范围"]}
  ]
}
```

用 [分发模板](dispatch.md) 将表格/记录的关键内容变成自包含提示词，不直接把整份大日志塞给每个子智能体。
