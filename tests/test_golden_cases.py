"""黄金用例：锁定 FORMAT_STYLE_SPEC.md 定义的排版契约。

用例编号与规格文档 §五 一一对应。任何改动后必须全绿。
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from formatter_core.lexer import tokenize
from formatter_core.main import format_sql_file


# ---------------------------------------------------------------- 用例 1-10
# CASE WHEN 三档排版（规格 §二）

CASE_SINGLE_NO_AND = "select case when a = 1 then 2 else 3 end as x from t"
CASE_SINGLE_ONE_AND = "select case when a = 1 and b = 2 then 3 else 0 end as x from t"
CASE_SINGLE_THREE_AND = (
    "select case when a = 1 and b = 2 and c = 3 then 4 else 0 end as x from t"
)
CASE_TWO_SHORT_ENUM = (
    "select case when a = 'A' then 1 when b = 'B' then 2 else 0 end as x from t"
)
CASE_TWO_ONE_AND_EACH = (
    "select case when a = 1 and b = 2 then 1 when c = 3 and d = 4 then 2 else 0 end as x from t"
)
# 复杂分支: 条件宽度超出 MAX_WIDTH (100) -> 触发拆分
CASE_TWO_MIXED_COMPLEX = (
    "select case when "
    + " and ".join(f"col_{i} = 'val_{i}'" for i in range(10))
    + " then 1 when d = 4 then 2 else 0 end as x from t"
)
CASE_WITH_OR = (
    "select case when a = 1 or b = 2 then 1 when c = 3 then 2 else 0 end as x from t"
)
# 含 OR 且超宽 -> 触发拆分
CASE_WITH_OR_WIDE = (
    "select case when "
    + " or ".join(f"col_{i} = 'val_{i}'" for i in range(10))
    + " then 1 when c = 3 then 2 else 0 end as x from t"
)
CASE_WITH_INLINE_COMMENT = (
    "select case when a = 1 -- 注释\n then 1 when b = 2 then 2 else 0 end as x from t"
)
CASE_WITH_SUBQUERY = (
    "select case when a in (select id from t2) then 1 when b = 2 then 2 else 0 end as x from t"
)
CASE_TWO_ON_ONE_LINE = (
    "select case when a = 1 then 1 end as x, case when b = 2 then 2 end as y from t"
)


def _lines(sql):
    return format_sql_file(sql).split("\n")


@pytest.mark.parametrize(
    "sql",
    [CASE_SINGLE_NO_AND, CASE_SINGLE_ONE_AND, CASE_SINGLE_THREE_AND],
    ids=["case-1-no-and", "case-2-one-and", "case-3-three-and"],
)
def test_case_single_branch_stays_on_one_line(sql):
    """用例 1-3：单分支 CASE 整块一行，不因 AND 数量拆行。"""
    out = _lines(sql)
    case_lines = [ln for ln in out if "case" in ln]
    assert len(case_lines) == 1, f"单分支 CASE 应只占一行，实际:\n{chr(10).join(out)}"
    assert re.match(r"^\s*case when .* then .* end as x$", case_lines[0]), case_lines[0]


def test_case_two_branches_each_on_own_line():
    """用例 4：多分支时每分支一行，且条件不展开。"""
    out = _lines(CASE_TWO_SHORT_ENUM)
    assert "   case" in out, out
    assert "     when a = 'A' then 1" in out, out
    assert "     when b = 'B' then 2" in out, out
    assert "     else 0" in out, out
    assert "   end as x" in out, out


def test_case_two_branches_with_one_and_each():
    """用例 5：每分支仅 1 个 AND 时条件不展开。"""
    out = _lines(CASE_TWO_ONE_AND_EACH)
    assert "     when a = 1 and b = 2 then 1" in out, out
    assert "     when c = 3 and d = 4 then 2" in out, out


def test_case_mixed_complex_only_complex_branch_splits():
    """用例 6：超宽分支拆分，简单分支不受影响（分支之间互相独立）。"""
    out = _lines(CASE_TWO_MIXED_COMPLEX)
    # 超宽分支: when 与首段同行, 其余段缩进, then 回到 when 基线
    assert any(ln.strip().startswith("when col_0 = 'val_0'") for ln in out), out
    assert any(ln.strip().startswith("and col_1 = 'val_1'") for ln in out), out
    assert any(ln.strip() == "then 1" for ln in out), out
    # 简单分支保持单行 —— 一个分支拆不拆, 不影响另一个分支
    assert any(ln.strip() == "when d = 4 then 2" for ln in out), out


def test_case_with_or_stays_on_one_line_when_it_fits():
    """用例 7：含顶层 OR 的短条件放一行 —— 宽度够就不拆。"""
    out = _lines(CASE_WITH_OR)
    assert any(ln.strip() == "when a = 1 or b = 2 then 1" for ln in out), out


def test_case_with_or_splits_when_too_wide():
    """用例 7b：含顶层 OR 且超宽时拆分。"""
    out = _lines(CASE_WITH_OR_WIDE)
    assert any(ln.strip().startswith("when col_0 = 'val_0'") for ln in out), out
    assert any(ln.strip().startswith("or col_1 = 'val_1'") for ln in out), out


def test_case_with_inline_comment_is_force_split():
    """用例 8：行内注释强制拆分（硬约束 H1），保证 then/end 不被注释吞掉。"""
    out = _lines(CASE_WITH_INLINE_COMMENT)
    # 注释之后的 then 必须另起一行，不能被 -- 吞掉
    assert any(ln.strip().startswith("then 1") for ln in out), out
    assert any(ln.strip() == "end as x" for ln in out), out


def test_case_with_subquery_keeps_case_keyword():
    """用例 9：CASE 内嵌子查询时不丢 case/end 关键字。"""
    out = _lines(CASE_WITH_SUBQUERY)
    stripped = [ln.strip() for ln in out]
    assert any(ln == "case" or ln.startswith("case ") for ln in stripped), out
    assert "end as x" in stripped, out


def test_two_independent_cases_on_one_line():
    """用例 10：单行两个独立 CASE，各自独立判定，互不污染。"""
    out = _lines(CASE_TWO_ON_ONE_LINE)
    assert "   case when a = 1 then 1 end as x" in out, out
    assert "  ,case when b = 2 then 2 end as y" in out, out


# ---------------------------------------------------------------- 用例 11-14
# 关键字分层（规格 §三）

def test_column_named_like_keyword_keeps_case():
    """用例 11：列名 count/length/date/max 保持原大小写 (Tier B 位置敏感)。"""
    out = format_sql_file(
        "select COUNT as cnt, Length as len, DATE as dt, MAX as mx from t"
    )
    for ident in ("COUNT", "Length", "DATE", "MAX"):
        assert re.search(rf"\b{ident}\b", out), f"{ident} 被改写了:\n{out}"


def test_function_call_is_lowercased():
    """用例 11 补充：同样的词作为函数调用时必须小写 (Tier B-1 规则)。"""
    out = format_sql_file(
        "select COUNT(*) as c, Length(x) as l, MAX(a) as m, SUM(b) as s from t"
    )
    for fn in ("count(*)", "length(x)", "max(a)", "sum(b)"):
        assert re.search(rf"\b{re.escape(fn)}", out), f"{fn} 未被小写:\n{out}"


def test_quoted_identifier_is_untouched():
    """用例 12：双引号标识符整段豁免，不做关键字替换。"""
    out = format_sql_file('select "SELECT" as kw, "MyCol" as c from t')
    assert '"SELECT"' in out, out
    assert '"MyCol"' in out, out


def test_window_function_lowercased_and_single_line():
    """用例 13：函数名小写，over 子句保持单行。"""
    out = format_sql_file(
        "select ROW_NUMBER() OVER(PARTITION BY a ORDER BY b DESC) as rn from t"
    )
    assert "row_number() over (partition by a order by b desc) as rn" in out, out


def test_identifier_case_preserved_in_group_by():
    """用例 14：group by 子句中的标识符不被小写。"""
    out = format_sql_file("select A.ID from T1 A group by A.ID")
    assert "A.ID" in out, out
    assert "a.id" not in out, out


# ---------------------------------------------------------------- 用例 15-16
# 幂等性与语义等价

_IDEMPOTENCY_SAMPLES = [
    CASE_SINGLE_NO_AND,
    CASE_SINGLE_THREE_AND,
    CASE_TWO_SHORT_ENUM,
    CASE_TWO_MIXED_COMPLEX,
    CASE_WITH_OR,
    CASE_WITH_OR_WIDE,
    CASE_TWO_MIXED_COMPLEX,
    CASE_WITH_INLINE_COMMENT,
    CASE_WITH_SUBQUERY,
    CASE_TWO_ON_ONE_LINE,
    "select count(*) as cnt, sum(amt) as total from t1 a "
    "left join t2 b on a.id = b.id where a.dt = '${d}' and a.flg in ('A','B','C','D','E','F') "
    "group by a.id order by cnt desc",
]


@pytest.mark.parametrize("sql", _IDEMPOTENCY_SAMPLES, ids=range(len(_IDEMPOTENCY_SAMPLES)))
def test_format_is_idempotent(sql):
    """用例 15：格式化幂等 —— format(format(x)) == format(x)。"""
    once = format_sql_file(sql)
    twice = format_sql_file(once)
    assert once == twice, f"幂等性破坏:\n--- round1 ---\n{once}\n--- round2 ---\n{twice}"


def _identifier_fingerprint(sql):
    """收集 SQL 中的标识符/数字集合（小写），用于语义等价校验。"""
    tokens = tokenize(sql)
    return {
        t["text"].lower()
        for t in tokens
        if t["type"] in {"word", "number", "quoted_id"}
    }


@pytest.mark.parametrize("sql", _IDEMPOTENCY_SAMPLES, ids=range(len(_IDEMPOTENCY_SAMPLES)))
def test_format_preserves_identifier_set(sql):
    """用例 16：语义等价 —— 标识符集合在格式化前后不变（仅大小写规范化）。"""
    before = _identifier_fingerprint(sql)
    after = _identifier_fingerprint(format_sql_file(sql))
    assert before == after, f"标识符集合被改变:\n丢失: {before - after}\n新增: {after - before}"


# ---------------------------------------------------------------- 通用哨兵
# 孤儿行检测（原则 P2）：输出中不应出现只含单个关键字的碎行。
# 注意：只针对"关键字独占一行"，标识符行（如表名 t）属合法短行，不算孤儿行。
# 顶级子句关键字 (select/from/where/...) 独占一行是规格要求的正常形态, 也不算孤儿行。

def test_no_orphan_lines():
    """通用性质：格式化结果不得产生只含单个关键字的孤儿行。"""
    from formatter_core.constants import ALL_KEYWORDS, LONE_LINE_KEYWORDS

    for sql in _IDEMPOTENCY_SAMPLES:
        for line in format_sql_file(sql).split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            low = stripped.lower()
            if low in LONE_LINE_KEYWORDS:
                continue
            if low in ALL_KEYWORDS:
                assert False, (
                    f"孤儿行(单关键字独占一行): {stripped!r}\n--- 全文 ---\n{format_sql_file(sql)}"
                )

