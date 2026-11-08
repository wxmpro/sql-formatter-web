# SQL 格式化排版风格规格（FORMAT_STYLE_SPEC）

> 版本：v1.0
> 起草日期：2026-11-08
> 适用范围：`sql-formatter-web/formatter_core/`
> 状态：**已实施**（阶段 0-4 全部落地，门禁全绿）

本文档是 `sql-formatter-web` 格式化引擎的**排版契约**。所有格式化行为以本文档为准；
引擎实现与本文档冲突时，以本文档为准并修订实现。

---

## 零、设计总则

### 0.1 三条第一性原则

| 原则 | 含义 | 反例 |
|------|------|------|
| **P1 语义单元优先** | 一行 = 一个完整语义单元，而不是"一个关键字" | `when` 独占一行、`then` 独占一行 |
| **P2 禁止孤儿行** | 任何渲染结果若产生有效内容 < `MIN_ATOM_WIDTH` 字符、或只含单个关键字的行，必须回收到父行 | `and b = 2` 单独成行（仅当该行是谓词链的一环时例外） |
| **P3 缩进跟随结构** | 缩进由该行所属的父层级决定，而非由前面有几个左括号决定 | 按括号 depth 累加缩进 |

### 0.2 "美观"的可操作定义

排版质量用三个可计算的指标衡量：

1. **无孤儿行** —— 不存在"去掉缩进后有效内容 ≤ 3 字符"、或"只含单个关键字"的行。
2. **无超宽行** —— 渲染结果不含超过 `MAX_WIDTH` 的行（`MIN_ATOM_WIDTH` 保护下的例外除外）。
3. **层级可预测** —— 同一层级的行缩进列相同；子层级的缩进恰好 +`INDENT_SPACES`。

### 0.3 两条硬约束（覆盖所有排版规则）

| 约束 | 原因 |
|------|------|
| **H1 行内 `--` 注释必须强制拆行** | 否则 `--` 会吞掉后续的 `then` / `else` / `end`，产出无法执行的 SQL |
| **H2 括号 / 引号 / `case`-`end` 必须配对** | 每次格式化后做静态检查，失败则整段回退原样 |

---

## 一、参数表

```python
INDENT_SPACES    = 2      # 一层逻辑缩进
MAX_WIDTH        = 100    # 行宽预算（对齐 05 仓库 MAX_COMMENT_ALIGN_COL）
MAX_AND_CHAIN    = 2      # 分支内顶层 AND 段数 ≥ 此值 → 触发条件拆分
OR_ALWAYS_SPLIT  = True   # 分支内出现顶层 OR → 一律拆分
MIN_ATOM_WIDTH   = 4      # 孤儿行判定阈值
IN_LIST_THRESHOLD = 5     # IN 列表元素数 > 此值 → 展开（已有）
```

---

## 二、CASE WHEN 排版契约（三档）

### 2.1 档位判定

```
analyze_case(tokens, case_idx) -> layout

1. 扫描到与 case 配对的 end，收集全部分支（when 分支 + else 分支）
2. 若分支总数 == 1 且该分支自然宽度 ≤ MAX_WIDTH        → D1
3. 否则进入 MULTI 模式，对每个分支独立判定是否拆分：
   a. 分支含行内 -- 注释                    → split = True   (H1)
   b. 分支自然宽度 > MAX_WIDTH               → split = True
   c. 否则                                    → split = False

> **规则演进（2026-11-08）**：旧规则还有"含顶层 OR 一律拆 / AND 段数 ≥ 2 就拆"。
> 这两条会让宽度完全够得下的条件也被拆开，产生 `when` 独占一行的孤儿形态，
> 与"判断语句少时放在一行"的排版诉求直接冲突。现统一由**宽度预算**决定：
> **宽度够就整行，超宽才拆**。AND / OR 段数不再单独触发拆分，只在超宽时
> 作为分段依据（拆成 `when <seg1>` / `and <seg2>` / `or <seg3>`）。

### 2.2 计数口径（实现必须严格遵守，否则行为会漂移）

| 项 | 定义 |
|----|------|
| `or_n` | 谓词**顶层**（不在任何括号内）的 OR 数量。`a and b or c` → `or_n = 1`。**不再单独触发拆分**，仅作超宽时的分段依据 |
| `and_n` | 顶层 OR 切分后，各 OR 段内 AND 数量的**最大值**。`a and b or c and d` → `and_n = 1`；`a and b and c` → `and_n = 2`。同样仅作分段依据 |
| `width` | 分支的自然渲染宽度（单空格连接）：`len("when " + cond + " then " + val)` |

### 2.3 渲染模板

```
── D1（单分支，整块一行）
   case when <cond> then <val> else <val> end as alias

── MULTI + split=False（条件不展开）
   case
     when <cond> then <val>
     when <cond> then <val>
     else <val>
   end as alias

── MULTI + split=True（条件超宽，按段展开）
   case
     when <seg1>
       and <seg2>
       and <seg3>
     then <val>
     else <val>
   end as alias
```

> `when` 始终与**第一个条件段同行**（不独占一行）。
>
> **原子括号组**：条件以 `(` 开头时，该逻辑分组括号在 CASE 条件区内保持
> **原子**——不展开、组内 and/or 不换行、组内 IN 列表也不展开，整体内联在
> `when (` 之后。段与段的分隔只由**顶层** and/or 负责：
>
> ```
> when (t1.split_flag = 'SP' or t1.split = 'SP')
>   and t2.itemcode in ('10001', '10002', '10003', '10004')
> then coalesce(t1.charge, 0)
> ```
>
> 非 CASE 场景下的逻辑分组括号仍按常规展开（`where (a = 1 or b = 2)`）。

**缩进基准**：`case` 与所在字段行对齐；`when` / `else` / `end` = `case` 基线 + `INDENT_SPACES`；
`and` 段 = `when` 基线 + `INDENT_SPACES`；`then <值>` 回到 `when` 基线。

### 2.4 与旧行为的差异

| 场景 | 旧（web 现状） | 新 |
|------|----------------|-----|
| 单分支 + 1 个 AND | 拆成 7 行 | **D1 整块一行** |
| 单分支 + 3 个 AND | 拆成 10 行 | **D1 整块一行** |
| 2 分支、枚举值短 | `when` / 条件 / `then 值` 三段式 | **`when <cond> then <val>` 同行** |
| 2 分支、每分支 3 个 AND | 三段式 | **两段式**（`when` 与首段同行，`then` 回 `when` 缩进） |

旧行为在三段式下产生 2 个孤儿行；新行为孤儿行数为 0。

---

## 三、关键字小写化契约（分层）

### 3.1 三层划分

| 层 | 成员 | 小写条件 |
|----|------|----------|
| **Tier A** 语法关键字 | `select/from/where/case/when/then/else/end/and/or/not/in/exists/between/like/is/null/distinct/union all/except/intersect/left join/right join/inner join/full join/outer join/cross join/group by/order by/having/limit/offset/insert into/delete from/update/set/values/with/as/on/using/over/partition by/…` 以及 DDL 类（`create/drop/alter/truncate/view/index/temporary/stored/clustered/distribute/skewed/primary/key/foreign/references/unique/constraint/comment/row/range/rows/unbounded/preceding/following/lateral`） | **无条件小写** |
| **Tier B-1** 函数名 | `count/sum/max/min/avg/length/lengthb/substring/substr/split/trim/ltrim/rtrim/round/floor/ceil/ceiling/abs/mod/power/sqrt/concat/upper/lower/coalesce/nvl/nvl2/ifnull/isnull/greatest/least/decode/cast/to_char/to_date/to_number/date_add/date_sub/datediff/date_format/months_between/add_months/from_unixtime/unix_timestamp/current_date/current_timestamp/sysdate/now/uuid/md5/row_number/rank/dense_rank/lag/lead/first_value/last_value/ntile/percent_rank/cume_dist/rowid/rownum/tdh_todate/…` | **仅当紧跟 `(`** |
| **Tier B-2** 类型名 | `int/integer/bigint/smallint/tinyint/float/double/decimal/numeric/string/varchar/char/boolean/binary/date/datetime/timestamp/array/map/struct/void` | **仅当处于类型位置**（前一个 token 是标识符） |
| **Tier C** 永不触碰 | 单引号字符串、双引号标识符、`` `反引号` ``、`[]`、别名 | 原样保留 |

### 3.2 关键约束

| # | 约束 |
|---|------|
| C1 | **双引号内容整段豁免**。ANSI SQL 中 `"foo"` 是标识符引用，不是字符串。旧实现会把它当字符串做关键字替换（`"SELECT"` → `"select"`），属缺陷 |
| C2 | **Tier B 函数名后面不跟 `(` 时视为列名**，保持原大小写。`select count from t` → `count` 不小写；`select count(*) from t` → `count` 小写 |
| C3 | **Tier B 类型名前一个 token 必须是标识符**，否则视为列名。`create table t (date int)` → 列名 `date` 保留，`int` 小写 |
| C4 | **别名原样保留**。`as CNT` / `as TotalAmt` 不小写 |
| C5 | `is_keyword` 属性保持原有语义（用于 FSM 结构判断），分层信息由新增的 `kw_class` 字段承载 |

### 3.3 相对 05 仓库的补齐

05 仓库 `SQL_KW` 有 150 个原子词，本项目原 `ALL_KEYWORDS` 只有 111 个，**缺 66 个**。
Tier A 补入其中语法类；Tier B 补入其中函数类与类型类。

---

## 四、全场景换行判定表

| 场景 | 规则 | 状态 |
|------|------|------|
| 顶级子句边界（select/from/where/group by/order by/having/join/on/union） | 换行，缩进归零 | 已有 ✓ |
| SELECT 字段列表 | 每字段一行，逗号顶格 | 已有 ✓ |
| WHERE 条件链 | ≥1 个顶层 AND/OR → 每个条件一行，缩进对齐；单条件 → 同行 | 已有 ✓ |
| 窗口函数 `over (...)` | 始终单行 | 已有 ✓ |
| IN 列表 | ≤ `IN_LIST_THRESHOLD` 元素单行；> 阈值展开，逗号顶格 | 需统一逗号风格 |
| 字段内简单子查询 `(select ...)` | 保持单行 | **需新增** |
| `select` 的修饰符 `distinct` | 与 `select` 同行 | **需新增** |
| 谓词动词 `exists` | 与 `where` 同行（其后子查询括号可另起一行） | **需新增** |
| 字段内复杂子查询 | 展开，`(` 与字段内容对齐 | 已有 |
| JOIN 表名 | 与 JOIN 关键字同行 | 已有（**有意与 05 仓库分歧**，见 §六） |
| DDL/DML 单行（`truncate table x;` / `use x;`） | 保持单行 | 已有 ✓ |

---

## 五、黄金用例清单

以下 16 条为**强制门禁**，任何改动后必须全绿。

| # | 场景 | 期望 |
|---|------|------|
| 1 | 单分支无 AND | D1 整块一行 |
| 2 | 单分支 1 个 AND | D1 整块一行 |
| 3 | 单分支 3 个 AND | D1 整块一行 |
| 4 | 2 分支、枚举值单字母 | MULTI，`when x = 'A' then 1` 同行 |
| 5 | 2 分支、每分支 1 个 AND | MULTI，条件不展开 |
| 6 | 2 分支、某分支条件超宽 | 该分支按段拆分，另一分支不受影响 |
| 7 | 分支含顶层 OR | 宽度够 → 整行；超宽 → 拆分 |
| 8 | 分支含行内 `--` 注释 | 强制拆分（H1） |
| 9 | CASE 内嵌子查询 | 拆分且不丢 `case` 关键字 |
| 10 | 单行两个独立 CASE | 两个 CASE 独立判定，不互相污染 |
| 11 | 列名为 `count` / `length` / `date` | 保持原大小写 |
| 12 | `"SELECT"` / `"MyCol"` | 原样不动 |
| 13 | `ROW_NUMBER() OVER (...)` | 函数名小写、`over` 子句单行 |
| 14 | `GROUP BY A.ID` | `A.ID` 不被小写 |
| 15 | 任意输入 | 幂等：`format(format(x)) == format(x)` |
| 16 | 任意输入 | 语义等价：代码 token **序列**不变（类型+文本+顺序+数量） |

---

## 六、与 05 仓库的有意分歧

决策：**web 作主干，搬规则不搬代码**。以下差异为**有意保留**，不向 05 仓库对齐：

| 项 | web | 05 v26 | 分歧理由 |
|----|-----|--------|----------|
| JOIN 表名 | `left join DW.T2 B` 同行 | `left join` ⏎ `DW.T2 B` | 同行更紧凑，减少换行（贴合 P1） |
| 标识符大小写 | 保留 `A.ID` | `group by` 子句会误小写为 `a.id` | web 语义安全 |
| 末尾分号 | 不补 | 补 `;` | web 处理的是片段，补分号会改变语句边界 |
| 引擎架构 | token / FSM | 行级正则 | web 在"不改语义"上更强 |

以下差异**向 05 仓库对齐**（阶段 4）：

- IN 列表展开的逗号风格统一为 `,` 顶格（与整仓 SELECT 字段风格一致）
- 字段内简单子查询保持单行

---

## 七、实施顺序与门禁

| 阶段 | 内容 | 门禁 | 状态 |
|------|------|------|------|
| 0 | 本文档 + 黄金用例硬编码 | 文档 review 通过 | ✅ |
| 1 | `fsm_core.py` 落地 §二 三档 CASE 排版 | 用例 1-10、15、16 全绿 | ✅ |
| 2 | `constants.py` 分层 + `lexer.py` 落地 §三 关键字分层 | 用例 11-14 全绿 | ✅ |
| 3 | 幂等性回归脚本 + 黄金用例接入 CI | 15、16 全绿 | ✅ |
| 4 | 补齐 §四 中标「需新增/需统一」的项 | 全量用例全绿 | ✅ |

**三道验收门禁（每阶段独立）**

1. 黄金用例全绿
2. 幂等：`round2 == round3`
3. 语义等价：格式化前后代码 token **序列**不变（类型+文本+顺序+数量）

### 实施落地位置

| 契约条款 | 实现位置 |
|----------|----------|
| §二 CASE 三档 | `formatter_core/fsm_core.py` — `analyze_case()` / `_slice_width()`；`FormatState.case_layouts` / `case_frames` |
| §三 关键字分层 | `formatter_core/constants.py` — `KEYWORD_TIER_A` / `KEYWORD_TIER_B_FUNC` / `KEYWORD_TIER_B_TYPE`；`formatter_core/lexer.py` — `classify_tokens()` |
| §三 C1 双引号豁免 | `formatter_core/lexer.py` — 移除 `lowercase_keywords_in_string()`，双引号内容整段不参与关键字替换 |
| §三 高亮一致性 | `formatter_core/highlighter.py` — 复用 `classify_tokens()`，列名不再被误高亮为关键字 |
| §四 简单子查询单行 | `formatter_core/fsm_core.py` — `_subquery_scope()`；`FormatState.simple_subq_flags` / `simple_subq_depth` |
| §五 黄金用例 | `tests/test_golden_cases.py`（16 条） |
| §七 回归门禁 | `tools/regression_check.py` + `tests/corpus/`（16 个语料）+ `.github/workflows/ci.yml` |

### 已知遗留缺陷（超出本规格范围，未修复）

| 缺陷 | 现象 | 备注 |
|------|------|------|
| PL/SQL 块内缩进丢失 | `declare` 之后的变量声明与 `end` 顶格，未按层级缩进 | PL/SQL 支持本身不完整（`begin` 走单行模式）。修复需重构块级缩进模型，风险高于收益，待专项处理 |
| PL/SQL `begin` 块合并为一行 | `begin select count ( * ) into v_cnt from ...;` | 同上 |
| 末尾分号不补 | 输出不追加 `;` | 有意为之，见 §六 |

---

## 八、幂等性契约与构造级根因（2026-11-08 全量归因）

> 本章记录对 3,888 个真实数仓脚本做全量归因后定位的**构造级**根因。
> 目的：让后续改动能预先知道"哪类构造会互相影响"，避免"修一个脚本、坏一片脚本"。

### 8.1 三道门禁（每条改动都必须全绿）

| 门禁 | 判定 | 实现 |
|------|------|------|
| G1 幂等 | `format(format(x)) == format(x)` | `tools/regression_check.py` |
| G2 语义等价 | 代码 token **序列**（类型+文本+顺序+数量）不变，仅大小写规范化 | 同上 + `batch_format.py` |
| G3 无孤儿行 | 不产生只含单个关键字的碎行 | 同上 |

> G2 用**序列**而非集合：集合只能发现"增删"，序列还能发现"顺序错乱"。
> G2 是防止内容丢失的最后防线 —— 本次正是它抓出了数字正则把 `1..` 吞成 `1.` 的缺陷。

### 8.2 全量归因结果

对 3,888 个源脚本的基线：**幂等性失败 1,143 (29.5%)**、内容变化 17、输出语法不完整 395。
逐层消融（monkeypatch 全量重跑）后确认**与 CASE/IN 列表/注释长度等风格规则无关**，
最终定位到以下 7 个**构造级**根因：

| # | 构造 | 症状 | 根因位置 | 修复 |
|---|------|------|----------|------|
| 1 | 注释出现位置不同 | 同一注释在 round1 独立成行、round2 合并回行尾 | `fsm_core` 有**两条**注释输出路径（`,` 分支特判 vs comment token 分支） | 统一到单一路径，删除 `,` 分支特判 |
| 2 | 注释长短判定 | 同一注释两轮判定结果不同 | 判定依赖"注释在代码中的位置"而非"注释自身长度" | 判定只依据注释正文长度（`COMMENT_INLINE_MAX`） |
| 3 | 长注释超宽 | 注释行被插到**代码行之前**，两轮行序不一致 | `aligner` 的 `target_col > 100` 分支 | 注释行改为**紧跟其代码行**（放代码行之后） |
| 4 | 字符串含 `--` | 语句被从中间劈开 | `aligner` 用 `line.split(' -- ', 1)` 切分 | 改用 `find_comment_start()` 扫描，跳过引号内容 |
| 5 | PL/SQL `BEGIN...END` | 392 个文件被误判语法错误、整段原样透传 | `syntax_check` 把 PL/SQL 的 `END` 当 CASE 的 `END` | BEGIN/END 与 CASE/END 分开计数 |
| 6 | `--` 注释后有代码 | 注释吞掉 `;`，语句边界丢失 | `--` 注释可与代码同行，但其后会话掉后续 token | 注释后若仍有代码 token（含 `;`）必须独立成行 |
| 7 | `1..tbl.col` / 数字 | 数字 token 被吞成 `1.`，内容改变 | lexer 数字正则 `\d+\.?\d*` | 改为 `\d+(?:\.\d+)?` |

另修两处**语义级**缺陷（由 G2 门禁抓出）：

- 双引号标识符被当字符串做关键字替换（`"SELECT"` → `"select"`）→ 整段豁免
- `normalize_tokens` 合并复合词时丢失 token 位置 → 合并词保留 `start`/`end`
  （否则容灾回退的"原文切片"会按错误位置截断内容）

### 8.3 修复后全量结果

| 指标 | 基线 | 修复后 |
|------|------|--------|
| 幂等性失败 | 1,143 (29.5%) | **0** |
| 代码 token 序列变化 | 17 | **0** |
| 输出语法不完整 | 395 | **3**（源文件自身括号不配对，原样透传） |
| 正常规范化 | 2,633 (67.7%) | **3,870 (99.6%)** |

### 8.4 后续改动必须遵守的约束

| 约束 | 说明 |
|------|------|
| C-1 注释只有一条输出路径 | 长短判定只看注释正文长度，与其在代码中的位置无关 |
| C-2 注释其后有代码 token 时必须独立成行 | `--` 会吞掉其后一切，`;` 也不例外 |
| C-3 注释必须跟随其代码行 | 任何情况下不得把注释行插到别的代码行之前 |
| C-4 切分代码与注释必须跳过引号 | 字符串里的 `--` 不是注释边界 |
| C-5 `END` 必须区分 CASE 与 PL/SQL | 二者分开计数，且多余的 END 不算错误 |
| C-6 lexer 不得改写 token 内容 | 数字正则不得吞小数点；双引号内容整段豁免 |
| C-7 合并复合词必须保留位置 | 否则回退切片会截断内容 |
| C-8 任何改动后必须跑全量 3,888 文件 | 单文件测试无法暴露构造级冲突 |
| C-9 条件拆分只由**宽度**与**行内注释**触发 | AND/OR 段数不再单独触发拆分，否则宽度够的条件也会被拆开 |
| C-10 不得改变 token 的渲染顺序 | 把注释前移（如移到 `then` 之前）会改变顺序，破坏幂等性；宁可让 `then` 独占一行 |
| C-11 CASE 条件区内的逻辑分组括号是**原子** | 不展开、组内不换行；段分隔只由顶层 and/or 负责，否则 `when` 会被留空独占一行 |

### 8.5 回归语料（覆盖上述全部构造）

`tests/corpus/` 共 16 个语料，其中新增的 4 个专门守护本次根因：

| 语料 | 守护的构造 |
|------|-----------|
| `14_comment_patterns.sql` | 行尾短/长注释、独立注释、字符串含 `--` |
| `15_plsql_block.sql` | PL/SQL BEGIN...END IF |
| `16_token_edge_cases.sql` | `${}` 占位符紧跟注释、`1..col`、引号标识符、关键字同形列名 |
| `17_case_mixed.sql` | CASE + 注释 + IN 列表 + 窗口函数组合 |

---

*本文档由 2026-11-08 的仓库分析与实测结论推导而成。相关实测样本见 `tests/test_golden_cases.py` 与 `tests/corpus/`。*
