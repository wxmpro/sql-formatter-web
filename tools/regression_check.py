#!/usr/bin/env python3
"""幂等性 + 语义等价回归检查 (FORMAT_STYLE_SPEC §七 门禁 2/3)。

对 tests/corpus/ 下每个 SQL 语料执行三轮格式化, 校验:
  门禁 2  幂等性    : round2 == round3
  门禁 3  语义等价  : 格式化前后标识符/字符串集合不变 (仅大小写规范化)
  性质    无孤儿行  : 不产生只含单个关键字的碎行

用法:
    python3 tools/regression_check.py
退出码 0 表示全部通过。
"""

import glob
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from formatter_core.constants import ALL_KEYWORDS, LONE_LINE_KEYWORDS  # noqa: E402
from formatter_core.lexer import tokenize  # noqa: E402
from formatter_core.main import format_sql_file  # noqa: E402

CORPUS_DIR = os.path.join(REPO_ROOT, "tests", "corpus")

# 顶级子句关键字独占一行是规格要求的正常形态, 不算孤儿行
_LEGAL_LONE_LINES = LONE_LINE_KEYWORDS


def fingerprint(sql):
    """收集标识符/数字/引用标识符集合 (小写), 用于语义等价校验。"""
    return {
        t["text"].lower()
        for t in tokenize(sql)
        if t["type"] in {"word", "number", "quoted_id"}
    }


def check_orphan_lines(formatted):
    """返回孤儿行列表 (只含单个关键字的碎行)。"""
    orphans = []
    for line in formatted.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if low in _LEGAL_LONE_LINES:
            continue
        if low in ALL_KEYWORDS:
            orphans.append(stripped)
    return orphans


def check_file(path):
    """返回该语料文件的失败原因列表 (空列表表示通过)。"""
    failures = []
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        round1 = format_sql_file(source)
        round2 = format_sql_file(round1)
    except Exception as exc:  # noqa: BLE001
        return [f"格式化异常: {exc}"]

    # 门禁 2: 幂等性
    if round1 != round2:
        failures.append("幂等性破坏: round1 != round2")

    # 门禁 3: 语义等价
    before = fingerprint(source)
    after = fingerprint(round1)
    if before != after:
        lost = sorted(before - after)
        added = sorted(after - before)
        failures.append(f"标识符集合改变: 丢失={lost} 新增={added}")

    # 性质: 无孤儿行
    orphans = check_orphan_lines(round1)
    if orphans:
        failures.append(f"孤儿行: {orphans}")

    return failures


def main():
    files = sorted(glob.glob(os.path.join(CORPUS_DIR, "*.sql")))
    if not files:
        print(f"⚠️  未找到回归语料: {CORPUS_DIR}")
        return 1

    passed = 0
    failed = 0
    failed_files = []

    for path in files:
        failures = check_file(path)
        if failures:
            failed += 1
            failed_files.append((os.path.basename(path), failures))
            print(f"  ✗ {os.path.basename(path)}")
            for reason in failures:
                print(f"      - {reason}")
        else:
            passed += 1
            print(f"  ✓ {os.path.basename(path)}")

    total = passed + failed
    print()
    print(f"总数: {total}  通过: {passed}  失败: {failed}")
    if failed_files:
        print("失败文件:")
        for name, reasons in failed_files:
            print(f"  ✗ {name}: {'; '.join(reasons)}")
        return 1
    print("✓ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
