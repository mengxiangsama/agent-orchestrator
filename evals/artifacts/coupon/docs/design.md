# 优惠券订单报价设计

## 1. 范围与现状

现有 `src/payment.py` 提供 `payable(subtotal, shipping)`，直接返回两者之和，未校验输入。本次仅交付设计，不修改该函数、不实现新接口、不添加或执行业务测试。

拟新增纯计算接口 `quote(subtotal, shipping, coupon=None)`。业务规则来自本次用户请求；报价不发起真实支付、不核销优惠券、不操作库存、不访问网络、不读写持久化状态，也不修改传入的映射。

## 2. 数据契约

所有金额的单位均为整数分，不使用浮点数、不做四舍五入、不隐式转换字符串或其他数值类型。Python 中 `bool` 是 `int` 的子类，必须单独排除。

| 项目 | 类型与约束 | 含义 |
| --- | --- | --- |
| `subtotal` | 必填；非负整数，排除布尔值 | 商品金额，不含运费 |
| `shipping` | 必填；非负整数，排除布尔值 | 运费 |
| `coupon` | 可省略，默认 `None`；否则须为 `collections.abc.Mapping` | `None` 表示无券；支持普通字典和只读映射 |
| `coupon.discount` | 有券时必填；非负整数，排除布尔值 | 券的固定优惠金额 |
| `coupon.minimum` | 有券时必填；非负整数，排除布尔值 | 使用券所需的最低商品金额 |
| `coupon.enabled` | 有券时必填；严格为 `bool` | 是否启用优惠券 |
| 返回值 | 非负整数，单位为分 | 优惠后的商品金额加运费 |

整数校验采用 `isinstance(value, int)` 且不是 `bool`，再检查 `value >= 0`。浮点数（包括 `100.0`）、字符串、`Decimal` 和 `None` 均不是合法金额；不新增金额上限，按 Python 整数语义计算。

为使接口可直接按此设计实现，本设计明确以下接口选择：

- 返回值采用单个整数总额；本次不设计报价明细对象。
- 非 `None` 的券对象必须且只能包含三个字符串键：`discount`、`minimum`、`enabled`。缺失字段、未知字段或非字符串键均拒绝，不设置隐含默认值。
- 空映射 `{}` 属于缺失字段，不等价于无券；只有 `None` 表示无券。
- 停用券仍须完整通过格式与字段校验，不能通过 `enabled=False` 绕过校验。

### 错误契约

不合法的输入显式抛出异常，不返回兜底金额，不静默忽略非法优惠券。

| 错误 | 异常 | 示例 |
| --- | --- | --- |
| 商品额、运费、优惠额或门槛的类型错误，包含布尔值 | `TypeError` | `subtotal=True`、`shipping=1.0`、`coupon.discount="100"` |
| 上述金额或门槛为负整数 | `ValueError` | `subtotal=-1`、`coupon.minimum=-1` |
| `coupon` 既不是 `None` 也不是映射 | `TypeError` | `False`、`[]`、列表形式的键值对、字符串 |
| 券缺失字段、出现未知字段或非字符串键 | `ValueError` | `{}`、缺少 `enabled`、额外包含 `code` |
| `enabled` 不是布尔值 | `TypeError` | `0`、`1`、`"false"`、`None` |

异常消息应指出参数或字段路径和违反的约束，例如 `coupon.discount must be a non-negative integer (bool is not allowed)`。消息不需要回显整个券对象。

多处错误时采用固定顺序，报告首先发现的错误：`subtotal` → `shipping` → `coupon` 容器类型 → 券的键集合 → `discount` → `minimum` → `enabled`。每个整数先检查类型，再检查是否为负数；缺失字段也应转换为上述明确的 `ValueError`，不泄漏偶然的 `KeyError`。

## 3. 算法

1. 按上述顺序校验 `subtotal`、`shipping`。若 `coupon` 不是 `None`，继续完整校验其结构和所有字段；有错即终止并抛出对应异常。
2. 初始化实际优惠额 `applied_discount = 0`。
3. 仅当券存在、`enabled` 为 `True` 且 `subtotal >= minimum` 时，令 `applied_discount = min(discount, subtotal)`。
4. 计算优惠后商品额 `goods_due = subtotal - applied_discount`。
5. 返回 `goods_due + shipping`。

等价公式：符合用券条件时，`total = max(subtotal - discount, 0) + shipping`；其他合法输入均为 `total = subtotal + shipping`。

门槛仅比较原始商品额，不把运费加入门槛，也不先扣优惠再判断门槛。优惠只能扣商品额，不能抵扣运费；优惠超过商品额的部分不产生负数、余额或找零。

由于 `0 <= applied_discount <= subtotal` 且 `shipping >= 0`，始终有 `shipping <= total <= subtotal + shipping`，因此返回值一定非负。校验负输入时必须直接拒绝，不能靠最终截断结果掩盖错误。

## 4. 边界与预期结果

以下金额均为分；表中的券以 `(discount, minimum, enabled)` 简写，实际输入必须是具有三个指定键的映射。

| 场景 | `subtotal` | `shipping` | 券 | 预期总额 |
| --- | --- | --- | --- | --- |
| 省略券参数 | 1000 | 200 | 省略 | 1200 |
| 显式无券 | 1000 | 200 | `None` | 1200 |
| 券停用，商品额已达门槛 | 1000 | 200 | `(300, 500, False)` | 1200 |
| 比门槛少一分 | 999 | 200 | `(300, 1000, True)` | 1199 |
| 刚好达到门槛 | 1000 | 200 | `(300, 1000, True)` | 900 |
| 比门槛多一分 | 1001 | 200 | `(300, 1000, True)` | 901 |
| 运费不参与凑门槛 | 900 | 200 | `(300, 1000, True)` | 1100 |
| 零门槛 | 1000 | 200 | `(300, 0, True)` | 900 |
| 零优惠 | 1000 | 200 | `(0, 0, True)` | 1200 |
| 优惠恰好等于商品额 | 1000 | 200 | `(1000, 0, True)` | 200 |
| 优惠超过商品额，运费仍需支付 | 1000 | 200 | `(5000, 0, True)` | 200 |
| 零商品额且零门槛 | 0 | 200 | `(500, 0, True)` | 200 |
| 商品额和运费均为零，无券 | 0 | 0 | `None` | 0 |
| 商品额和运费均为零，有券 | 0 | 0 | `(500, 0, True)` | 0 |
| 零运费 | 1000 | 0 | `(300, 1000, True)` | 700 |
| 大整数精确运算 | `10**30` | 7 | `(3, 0, True)` | `10**30 + 4` |

## 5. 测试建议与验收标准

未来实现时建议使用参数化单元测试，覆盖上表全部结果，并分别验证省略 `coupon` 和显式传入 `None`。

非法输入测试须断言异常类型及消息中的字段定位：

- 对 `subtotal`、`shipping`、`discount`、`minimum` 分别替换为 `True`、`False`、`1.0`、`"1"`、`None`、列表、`Decimal("1")`，预期 `TypeError`；分别替换为 `-1`，预期 `ValueError`。其他输入保持合法，避免错误被前序校验遮挡。
- 对 `coupon` 分别传入 `False`、`0`、空列表、键值对列表、字符串，预期 `TypeError`；空映射、分别缺少三个必填字段、未知字段、非字符串键，预期 `ValueError`。
- 对 `enabled` 分别传入 `0`、`1`、`"true"`、`"false"`、`None`，预期 `TypeError`；合法 `True` 和 `False` 分别验证启用与停用行为。
- 在 `enabled=False` 时重复非法 `discount`、非法 `minimum`、缺失字段和未知字段的案例，仍须抛出对应异常。商品额未达门槛时，也必须拒绝非法券字段。
- 构造多处错误，验证固定校验顺序，例如 `subtotal=True` 且券为空映射时，先报告 `subtotal` 的 `TypeError`。

补充契约与性质测试：

- 普通 `dict` 与 `types.MappingProxyType` 等合法映射应得到相同结果；调用前后券内容一致，重复调用结果一致。
- 对合法输入断言结果为整数且不是布尔值，并满足 `shipping <= total <= subtotal + shipping`。
- 无券、合法停用券及未达门槛的合法券，总额必须等于 `subtotal + shipping`。
- 符合用券条件时，实际优惠应为 `min(discount, subtotal)`；固定其他合法输入，增加运费 `k >= 0` 后，总额应恰好增加 `k`，优惠资格不变。
- 不应断言总额随商品额始终单调递增：跨过门槛时，优惠生效可能让总额下降。

本设计为未来新增 `quote` 提供契约；现有 `payable` 的迁移与调用方改造不属于本次交付。验收以接口、校验、公式、异常和测试预期覆盖用户规则为准；此文档不代表新接口已经实现或测试已经通过。
