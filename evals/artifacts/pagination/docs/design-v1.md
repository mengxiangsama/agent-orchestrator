# D1 候选设计 v1 / 尝试 2

状态：submitted，等待主智能体验收，不代表 accepted。任务 D1 无前置任务。本稿只包含设计与后续验收清单，未编写实现或测试文件，未执行功能验证。

本稿修正第 1 次设计的授权故障注入：首稿故意遗漏非法参数处理，已被主智能体拒绝。首稿 `docs/design-attempt-1.md` 作为历史证据保留，不修改。

## 接口与规则

接口：`pagination.paginate(records, page, page_size)`。实现文件约定为 `pagination.py`，仅使用 Python 标准库。

|规则|设计约束|
|---|---|
|R1|`records` 必须为 list，每条记录为含整数 `id` 的 dict；整个调用过程不修改原列表及记录内容，包括异常退出时。|
|R2|按 `id` 升序排序，再返回指定页的记录列表。|
|R3|`page` 必须为严格 int 且大于等于 1；`page_size` 必须为严格 int 且在闭区间 1～100。|
|R4|任何非法参数均抛出 `ValueError("INVALID_ARGUMENT")`，包括结构、字段、整数类型、页码和页大小错误。|
|R5|所有输入均通过校验后，超出页数返回空列表。|
|R6|`id` 为 1～5，`page=2, page_size=2` 时，返回 `id` 为 3、4 的记录，顺序为 3、4。|

严格整数采用 `type(value) is int`，因此 bool、浮点数、字符串及 int 子类均不接受；不做字符串转数字、浮点截断等隐式转换。容器采用 `isinstance(records, list)` 与 `isinstance(record, dict)` 判定，不额外限定容器必须是精确内建类型。

负数 `id`、零 `id`、重复 `id` 均允许，不去重。额外字段完整保留。排序稳定，相同 `id` 的记录保持原始相对顺序。

返回一个独立的列表容器；其中记录字典允许复用输入对象，不要求深拷贝。这里保证调用期间不修改输入，不承诺调用结束后修改返回记录不会影响原记录。

## 校验顺序与实现步骤

1. 检查 `records` 是否为 list；失败即抛出统一的 `ValueError("INVALID_ARGUMENT")`。
2. 检查 `page` 是否为严格 int 且 `page >= 1`；失败即抛出同一异常。
3. 检查 `page_size` 是否为严格 int 且 `1 <= page_size <= 100`；失败即抛出同一异常。
4. 遍历全部输入记录：每条必须为 dict，必须包含键 `id`，且该值必须满足 `type(record["id"]) is int`。任一检查失败即抛出同一异常。检查键存在后才访问该值，避免让缺键错误表现为 `KeyError`。
5. 只有全部参数和全部记录都通过校验后，才使用 `sorted(records, key=lambda record: record["id"])` 生成新的升序列表。
6. 计算 `start = (page - 1) * page_size`，`end = start + page_size`，返回排序结果的 `[start:end]` 切片。

发现非法输入时可以立即失败；“全部校验”要求每次成功返回前所有参数与所有记录均已验证，不要求收集所有错误。

空列表也必须先验证页码与页大小。不得因 `records` 为空、请求越界或只需某一页而提前成功返回；即使错误记录位于目标页之外，也必须抛出统一异常。该顺序防止越界返回掩盖非法记录，或排序时泄漏结构错误引起的其他异常。

处理过程中不调用原列表的原地排序，不增删元素，不改写记录字段。无需对输入做深拷贝。校验为 `O(n)`，排序为 `O(n log n)`，额外空间为 `O(n)`。

## 合法输入及分页边界验收清单

以下均为待执行用例，不代表已通过。执行时先 `from pagination import paginate`，令 `ids(result)` 表示 `[record["id"] for record in result]`。每一行独立调用并比对输出；额外字段及重复值场景同时比较完整记录。

|编号|可执行调用或输入|断言|
|---|---|---|
|A1 / R2、R6|`paginate([{"id":5},{"id":1},{"id":4},{"id":2},{"id":3}], 2, 2)`|`ids(result) == [3,4]`|
|A2 / R3|`paginate([{"id":3},{"id":1},{"id":2}], 1, 2)`|`ids(result) == [1,2]`|
|A3 / R5|`paginate([{"id":5},{"id":1},{"id":4},{"id":2},{"id":3}], 3, 2)`|`ids(result) == [5]`，尾页不补齐|
|A4 / R5|`paginate([{"id":1},{"id":2}], 2, 2)`|`result == []`，刚好越界|
|A5 / R5|`paginate([{"id":1}], 10**30, 1)`|`result == []`，极大合法页码|
|A6 / R1、R5|`paginate([], 1, 2)`|`result == []`|
|A7 / R3|`paginate([{"id":3},{"id":1},{"id":2}], 2, 1)`|`ids(result) == [2]`，最小页大小|
|A8 / R3|`paginate([{"id":i} for i in range(101,0,-1)], 1, 100)`|`ids(result) == list(range(1,101))`，最大页大小|
|A9 / R3、R5|`paginate([{"id":i} for i in range(101,0,-1)], 2, 100)`|`ids(result) == [101]`|
|A10 / R1、R2|`paginate([{"id":2,"tag":"a"},{"id":-1},{"id":0},{"id":2,"tag":"b"}], 1, 100)`|完整输出为 `[{"id":-1},{"id":0},{"id":2,"tag":"a"},{"id":2,"tag":"b"}]`|
|A11 / R1|`records=[{"id":2,"extra":{"v":[1]}},{"id":1,"name":"one"}]`；先保存 `copy.deepcopy(records)` 与每项对象引用，再调用 `paginate(records,1,1)`|原列表深值、元素顺序及逐项对象引用均保持；返回列表 `is not records`；返回记录额外字段完整|

## 非法参数及验证顺序验收清单

每行、每个候选值都是独立用例，均要求实际捕获 `ValueError`，且 `str(error) == "INVALID_ARGUMENT"`、`error.args == ("INVALID_ARGUMENT",)`。调用正常返回、异常类型不符或消息不符均判失败。

|编号|可执行调用或输入|覆盖点|
|---|---|---|
|E1 / R4|对 `bad` 分别取 `None`、`()`、`{}`、`"records"`、`1`，执行 `paginate(bad,1,2)`|records 必须为 list|
|E2 / R4|对 `bad` 分别取 `None`、`1`、`[]`、`"record"`，执行 `paginate([bad],1,2)`|每条记录必须为 dict|
|E3 / R4|`paginate([{"name":"missing"}],1,2)`|记录必须包含 id；不能泄漏 KeyError|
|E4 / R4|对 `bad` 分别取 `None`、`"1"`、`1.0`、`True`、`False`，执行 `paginate([{"id":bad}],1,2)`|id 必须为严格 int|
|E5 / R3、R4|对 `bad` 分别取 `0`、`-1`、`None`、`"1"`、`1.0`、`True`、`False`，执行 `paginate([{"id":1}],bad,2)`|页码类型及下界|
|E6 / R3、R4|对 `bad` 分别取 `0`、`-1`、`101`、`None`、`"2"`、`2.0`、`True`、`False`，执行 `paginate([{"id":1}],1,bad)`|页大小类型及上下界|
|E7 / R4|定义 `class IntChild(int): pass`；分别执行 `paginate([{"id":IntChild(1)}],1,2)`、`paginate([],IntChild(1),2)`、`paginate([],1,IntChild(2))`|严格 int，不接受 int 子类|
|E8 / R4|分别执行 `paginate([],0,2)`、`paginate([],1,101)`、`paginate([],True,2)`、`paginate([],1,False)`|空列表不得跳过参数校验|
|E9 / R4|`paginate([{"id":1},{}],999,1)`|越界不得跳过记录校验|
|E10 / R4|`paginate([{"id":1},{"id":"2"}],1,1)`|目标页之外的记录仍须校验|
|E11 / R1、R4|`records=[{"id":2},{"id":1},{}]`；先保存深值与逐项对象引用，再调用 `paginate(records,1,1)` 并捕获异常|异常退出后原列表顺序、元素引用及字段内容全部不变|

## 交接条件

主智能体应逐项核对本设计与 R1～R6，确认首稿保留、第二稿修正完整后才能决定是否 accepted。实现任务 I1 依赖设计获得 accepted；本稿的 submitted 状态不满足启动条件。实现者应依据上述步骤实现，测试者将这些用例转为 Python 标准库可执行断言。本文未启动 I1，也未创建任何实现或测试文件。
