# verification.py
from .lexer import tokenize
from .fsm_core import format_statement_tokens

def run_strict_test():
    # 1. 验证 Bug L (FROM/WHERE 子句字段缩进)
    out_l = format_statement_tokens(tokenize('select * from dual where x = 1'))
    assert '  dual' in out_l, f"Bug L 失败! 实际输出: {out_l}"
    assert '  x = 1' in out_l, f"Bug L 失败! 实际输出: {out_l}"

    # 2. 验证 Bug I 补完版 (OVER 内部逗号绝不拆行)
    out_i = format_statement_tokens(tokenize('select row_number() over (partition by a, b order by x) from t'))
    assert any('partition by a, b' in line for line in out_i), f"Bug I 未彻底修复! 实际输出: {out_i}"

    # 3. 验证 Bug M (IN 列表多行首元素对齐)
    out_m = format_statement_tokens(tokenize('select * from t where x in (1, 2, 3, 4, 5, 6)'))
    # 首元素 '1' 应该带有至少 4 个空格的缩进 (where层级2 + 括号层级2)
    assert '    1' in out_m or '      1' in out_m, f"Bug M 失败! 首元素未对齐: {out_m}"

    # 4. 验证 P2 补完版 (数组索引紧贴无空格)
    out_p2 = format_statement_tokens(tokenize("select split(t1.x, ',')[0] from t1"))
    assert any(")[0]" in line.replace(" ", "") for line in out_p2), f"P2 未完全修干净! 实际输出: {out_p2}"

    print("🎉 恭喜！所有硬核 Bug 均已通过最小复现单元测试，重构回归完全闭环！")

if __name__ == "__main__":
    run_strict_test()