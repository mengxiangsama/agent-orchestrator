# 工具异常（保留，不隐藏）

在记录 D1 拒绝事件时，主智能体首次尝试用同一 apply_patch 对 run.json 同时 Delete/Add，被工具拒绝：
`apply_patch verification failed: invalid patch: multiple operations target <TEMP_WORKSPACE>/run.json`。
该调用未改变 run.json，d1-rejection.md 已由前一个独立调用成功写入。
随后主智能体读取真实 run.json，以 Update File 应用同一事件记录；未更改事件含义或伪造已执行状态。
这是主智能体保存记录的工具使用错误，不是子任务尝试，也不是预设的故障注入。
