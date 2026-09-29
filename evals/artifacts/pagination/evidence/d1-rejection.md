# D1 首稿验收：拒绝，需返工

主智能体观察时间：2026-09-29 01:34:02 UTC。
真实子智能体：/root/pagination_design_test；尝试 1；提交状态 submitted。

主智能体已执行 `nl -ba docs/design-attempt-1.md`，逐行阅读 1—50 行；退出码 0。
`shasum -a 256 docs/design-attempt-1.md` 退出码 0，结果：
`c564379488f5ce402cb8916c7d98a9863d7569813c4f7e4ae921964bc3be5a6d`。

不合格项：requirements.md R4 要求非法参数抛出 ValueError("INVALID_ARGUMENT")。
首稿第 9 行只有合法输入范围，第 23—31 行和 37—48 行的边界/验收建议未包含非法输入处理，全文没有异常类型、消息和参数校验顺序。
这是真实文件中按用户授权故意注入的遗漏，不是自然发现的缺陷。

决定：submitted -> rework。I1 尚未创建，不允许启动。
返工通过标准：完整覆盖严格整数类型、页码/大小边界、records/list/dict/id 结构校验，统一异常消息；空列表或越界也不得跳过校验；补充对应验收用例。
保留首稿不改写，第二次提交至 docs/design-v1.md；第二次为本任务最后一次允许尝试。
