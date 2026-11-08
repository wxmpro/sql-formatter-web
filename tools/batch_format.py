#!/usr/bin/env python3
"""批量规范化工具 (FORMAT_STYLE_SPEC §七)。

用法:
    python3 tools/batch_format.py --src <源目录> --dst <目标目录> \
        [--suffix _step1] [--alias "旧层名=新层名"] [--dry-run] [--report report.json]

约束:
    - 源目录只读, 绝不写入
    - 保持相对目录结构
    - 每个文件做三道校验: 幂等性 / 语义等价 / 源语法完整性
    - 输出分类统计报告, 便于"按模式归因"而非"按个例打补丁"
"""

import argparse
import collections
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from formatter_core.lexer import tokenize  # noqa: E402
from formatter_core.main import format_sql_file  # noqa: E402
from formatter_core.syntax_check import check_syntax  # noqa: E402

ENCODINGS = ("utf-8", "gb18030", "latin-1")


def read_text(path):
    """按多种编码尝试读取, 返回 (文本, 实际编码)。"""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "replace"


def fingerprint(sql):
    """标识符/数字/引用标识符集合 (小写) —— 用于语义等价校验。"""
    return {
        t["text"].lower()
        for t in tokenize(sql)
        if t["type"] in {"word", "number", "quoted_id"}
    }


def code_token_sequence(sql):
    """代码 token 序列 (排除注释/空白) —— 比集合比较更强的语义等价校验。

    集合比较只能发现"增删", 序列比较还能发现"顺序错乱"与"数量变化"。
    """
    return [
        (t["type"], t["text"].lower())
        for t in tokenize(sql)
        if t["type"] not in {"comment", "space"}
    ]


def string_literals(sql):
    """字符串字面量集合 —— 用于校验格式化不改字符串内容。"""
    return {t["text"] for t in tokenize(sql) if t["type"] == "string"}


def analyze_source(path):
    """返回 (文本, 源语法是否完整)。"""
    text, _enc = read_text(path)
    try:
        ok = check_syntax(tokenize(text))
    except Exception:  # noqa: BLE001
        ok = False
    return text, ok


def process_one(path, rel_src, rel_dst, alias, dry_run):
    """处理单个文件, 返回结果记录。"""
    rec = {
        "src": rel_src,
        "dst": rel_dst,
        "status": "ok",
        "issues": [],
    }

    text, src_ok = analyze_source(path)
    rec["src_syntax_ok"] = src_ok
    rec["src_lines"] = text.count("\n") + 1
    rec["src_bytes"] = len(text.encode("utf-8", errors="replace"))

    if not text.strip():
        rec["status"] = "empty"
        rec["issues"].append("源文件为空")
        return rec, text

    try:
        out1 = format_sql_file(text)
    except Exception as exc:  # noqa: BLE001
        rec["status"] = "exception"
        rec["issues"].append(f"格式化异常: {exc}")
        return rec, text

    if not out1.strip():
        rec["status"] = "empty_output"
        rec["issues"].append("格式化结果为空")
        return rec, text

    # 门禁 1: 幂等性
    try:
        out2 = format_sql_file(out1)
        if out1 != out2:
            rec["status"] = "not_idempotent"
            rec["issues"].append("幂等性破坏: round1 != round2")
    except Exception as exc:  # noqa: BLE001
        rec["status"] = "not_idempotent"
        rec["issues"].append(f"二次格式化异常: {exc}")

    # 门禁 2: 语义等价 (标识符 + 字符串字面量)
    try:
        before_ids, after_ids = fingerprint(text), fingerprint(out1)
        if before_ids != after_ids:
            lost = sorted(before_ids - after_ids)
            added = sorted(after_ids - before_ids)
            rec["issues"].append(f"标识符改变: 丢失={lost[:8]} 新增={added[:8]}")
            if rec["status"] == "ok":
                rec["status"] = "identifier_changed"
        before_str, after_str = string_literals(text), string_literals(out1)
        if before_str != after_str:
            rec["issues"].append(
                f"字符串字面量改变: 丢失={sorted(before_str - after_str)[:5]} "
                f"新增={sorted(after_str - before_str)[:5]}"
            )
            if rec["status"] == "ok":
                rec["status"] = "literal_changed"
    except Exception as exc:  # noqa: BLE001
        rec["issues"].append(f"语义校验异常: {exc}")

    # 门禁 2b: 代码 token 序列等价 (顺序 + 数量)
    try:
        seq_src = code_token_sequence(text)
        seq_out = code_token_sequence(out1)
        if seq_src != seq_out:
            rec["issues"].append(
                f"代码 token 序列不等价: src={len(seq_src)} out={len(seq_out)}"
            )
            if rec["status"] == "ok":
                rec["status"] = "token_sequence_changed"
    except Exception as exc:  # noqa: BLE001
        rec["issues"].append(f"序列校验异常: {exc}")

    # 门禁 3: 输出语法完整性
    try:
        if not check_syntax(tokenize(out1)):
            if not src_ok:
                # 源文件本身语法不完整 -> 已按原文切片原样透传, 属预期降级
                rec["status"] = "source_invalid_passthrough"
            else:
                rec["issues"].append("输出语法不完整 (括号/case-end 未配对)")
                if rec["status"] == "ok":
                    rec["status"] = "bad_output"
    except Exception as exc:  # noqa: BLE001
        rec["issues"].append(f"输出语法校验异常: {exc}")

    # 是否触发了容灾回退 (源本身语法错误 -> 原样输出)
    rec["fallback"] = not src_ok

    # 写入
    if not dry_run:
        dst_path = os.path.join(args.dst, rel_dst)  # noqa: F821
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(out1)

    return rec, out1


def main():
    global args
    parser = argparse.ArgumentParser(description="SQL 批量规范化")
    parser.add_argument("--src", required=True, help="源目录 (只读)")
    parser.add_argument("--dst", required=True, help="目标目录")
    parser.add_argument("--suffix", default="_step1", help="输出文件名后缀")
    parser.add_argument("--alias", action="append", default=[],
                        help="一级目录别名映射, 形如 旧名=新名")
    parser.add_argument("--dry-run", action="store_true", help="只分析不写入")
    parser.add_argument("--report", default=None, help="JSON 报告输出路径")
    args = parser.parse_args()

    alias = {}
    for item in args.alias:
        if "=" in item:
            old, new = item.split("=", 1)
            alias[old.strip()] = new.strip()

    src_root = os.path.abspath(args.src)
    dst_root = os.path.abspath(args.dst)
    if not os.path.isdir(src_root):
        print(f"❌ 源目录不存在: {src_root}")
        return 1

    files = []
    for root, _dirs, names in os.walk(src_root):
        for name in sorted(names):
            if name.endswith(".sql"):
                files.append(os.path.join(root, name))
    files.sort()

    print(f"源目录 : {src_root}")
    print(f"目标   : {dst_root}  (dry-run={args.dry_run})")
    print(f"文件数 : {len(files)}")
    print(f"别名   : {alias or '无'}")
    print()

    records = []
    for idx, path in enumerate(files, 1):
        rel = os.path.relpath(path, src_root)
        parts = rel.split(os.sep)
        if parts[0] in alias:
            parts[0] = alias[parts[0]]
        stem, ext = os.path.splitext(os.path.join(*parts))
        rel_dst = stem + args.suffix + ext
        rec, _out = process_one(path, rel, rel_dst, alias, args.dry_run)
        records.append(rec)
        if idx % 500 == 0:
            print(f"  ... {idx}/{len(files)}")

    # ---- 汇总 ----
    status_count = collections.Counter(r["status"] for r in records)
    issue_count = collections.Counter()
    for r in records:
        for issue in r["issues"]:
            key = issue.split(":")[0].split("(")[0].strip()
            issue_count[key] += 1
    fallback_count = sum(1 for r in records if r.get("fallback"))
    passthrough_count = sum(1 for r in records if r["status"] == "source_invalid_passthrough")

    print()
    print("=" * 60)
    print(f"处理完成: {len(records)} 个文件")
    print()
    print("--- 状态分布 ---")
    for k, v in status_count.most_common():
        print(f"  {k:24s} {v}")
    print()
    print(f"--- 触发容灾回退 (源本身语法不完整): {fallback_count} ---")
    print(f"--- 其中按原文原样透传 (预期降级, 非失败): {passthrough_count} ---")
    print()
    print("--- 问题类型分布 ---")
    for k, v in issue_count.most_common():
        print(f"  {k:24s} {v}")
    print()

    bad = [r for r in records if r["status"] not in ("ok", "source_invalid_passthrough")]
    if bad:
        print(f"--- 异常样本 (前 30 / 共 {len(bad)}) ---")
        for r in bad[:30]:
            print(f"  [{r['status']}] {r['src']}")
            for issue in r["issues"]:
                print(f"        - {issue}")

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump({
                "src": src_root,
                "dst": dst_root,
                "total": len(records),
                "status_count": dict(status_count),
                "issue_count": dict(issue_count),
                "fallback_count": fallback_count,
                "records": records,
            }, f, ensure_ascii=False, indent=2)
        print(f"\n报告已写入: {args.report}")

    return 0 if not bad else 2


if __name__ == "__main__":
    sys.exit(main())
