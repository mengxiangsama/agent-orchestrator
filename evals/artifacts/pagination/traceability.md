# 业务规则 → 设计 → 实现 → 实测

本表由主智能体在 D1 v1、I1 v1 均验收后整合；不是子智能体自报通过。
主智能体合并运行 37 个 unittest 测试方法，exit_code=0；完整输出见 evidence/main-integration-tests.json。
20 个独立方法中包含固定种子 290926 的150组输入，属于其中一个方法的子用例，不另报为150个独立测试方法。

|用户规则|设计条目（docs/design-v1.md）|实现（pagination.py）|主要独立测试（qa/test_independent.py）|实际结果|
|---|---|---|---|---|
|R1：含整数id的记录列表，输入不变|接口规则R1；步骤1、4；A11/E11|第10—21行校验；23行sorted新列表|test_no_input_mutation_r1；test_invalid_record_container；test_invalid_record_shape；test_invalid_id_type；test_result_is_new_list|通过，深值/引用顺序/错误返回均核对|
|R2：id升序、仅指定页|R2；步骤5—6；A1/A2|第23—25行|test_unsorted_input_r2；test_seeded_pagination_properties|通过，包含150组固定种子输入|
|R3：page>=1，page_size整数1..100|R3；步骤2—3；A7—A9/E5—E7|第12—15行|test_page_size_boundaries_r3；test_invalid_page_r4；test_invalid_page_size_r4；test_accepted_design_int_subclass_rejection|通过，含1/100合法边界、0/101非法边界、bool/浮点/字符串|
|R4：非法参数统一ValueError("INVALID_ARGUMENT")|R4；步骤1—4；E1—E11|第10—21行所有异常分支|全部test_invalid_*；test_all_records_validated_even_outside_page|通过；实现方assert_invalid另检查精确异常类型与args|
|R5：超出页数返回[]|R5；A4/A5/A6|第24—25行|test_page_beyond_end_r5；test_large_page；test_empty_input；test_last_partial_page|通过；另验空/越界不绕过非法参数校验|
|R6：id1..5，page2/size2输出3、4|R6；A1|第23—25行|test_required_example_r6；test_unsorted_input_r2|通过；实现方test_fixture_second_page_preserves_labels也通过|

附加明确技术约定：严格int排除bool/int子类；list/dict容器子类允许；负数/重复id可用；同id排序稳定；额外字段保留；返回记录不保证深拷贝隔离。
这些是临时测试项目的接口细化，不是给 现有项目 增加业务规则。

## 编排验收对应

|场景|通过条件|实际证据|
|---|---|---|
|成果不合格返工|主智能体读取首稿，拒绝R4遗漏，仍不启动I1|evidence/d1-rejection.md；首稿哈希不变|
|重新验收|D1二稿完整且主智能体逐项核验|evidence/d1-acceptance-v1.md；D1验收版本1|
|依赖启动|I1启动晚于D1 accepted，传递准确版本|timeline事件6→7；run.json两次I1 start均带D1:1；实现方核验相同哈希|
|执行失败|真实缺文件exit1，停止，不造输入、不写实现|evidence/i1-attempt-1.json；main-missing-input-probe.json；list_agents completed|
|恢复与重试|主智能体确认失败后恢复输入，再派第2次|evidence/i1-recovery.md；main-recovery-probe.json；timeline事件8→9|
|主智能体独立验收|读取实现并自行运行测试，再accept|evidence/main-validation-1.json、main-validation-2.json；i1-acceptance-v1.md|
|整合|设计、实现、测试和用户规则一致|本表；evidence/main-integration-tests.json，37方法通过|

记录检查不等于工具执行认证；真实创建、分发、返回和执行结果同时保存在本次对话工具记录中。
