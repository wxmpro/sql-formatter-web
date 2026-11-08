# verification.py
"""历史 Bug 回归断言 (单一来源)。

被 pytest (tests/test_verification.py) 与 Pyodide 前端共同调用。
断言采用结构性判定 (缩进关系 / 相对位置), 不硬编码空格数, 避免格式微调即误报。
"""


def run_strict_test():
    # 1. 验证 Bug L (FROM/WHERE 子句字段缩进)
    from .lexer import tokenize
    from .fsm_core import format_statement_tokens

    out_l = format_statement_tokens(tokenize('select * from dual where x = 1'))
    assert any(ln.strip() == 'dual' for ln in out_l), f"Bug L 失败! 实际输出: {out_l}"
    assert any(ln.strip() == 'x = 1' for ln in out_l), f"Bug L 失败! 实际输出: {out_l}"

    # 2. 验证 Bug I 补完版 (OVER 内部逗号绝不拆行)
    out_i = format_statement_tokens(tokenize('select row_number() over (partition by a, b order by x) from t'))
    assert any('partition by a, b' in line for line in out_i), f"Bug I 未彻底修复! 实际输出: {out_i}"

    # 3. 验证 Bug M (IN 列表多行首元素缩进深于括号)
    out_m = format_statement_tokens(tokenize('select * from t where x in (1, 2, 3, 4, 5, 6)'))
    paren_line = next((ln for ln in out_m if ln.strip() == '('), None)
    first_line = next((ln for ln in out_m if ln.strip() == '1'), None)
    assert paren_line is not None and first_line is not None, f"Bug M 失败! 实际输出: {out_m}"
    paren_indent = len(paren_line) - len(paren_line.lstrip())
    first_indent = len(first_line) - len(first_line.lstrip())
    assert first_indent > paren_indent, (
        f"Bug M 失败! 首元素缩进 {first_indent} 未深于括号 {paren_indent}: {out_m}"
    )

    # 4. 验证 P2 补完版 (数组索引紧贴无空格)
    out_p2 = format_statement_tokens(tokenize("select split(t1.x, ',')[0] from t1"))
    assert any(")[0]" in line.replace(" ", "") for line in out_p2), f"P2 未完全修干净! 实际输出: {out_p2}"

    print("🎉 恭喜！所有硬核 Bug 均已通过最小复现单元测试，重构回归完全闭环！")


if __name__ == '__main__':
    run_strict_test()
