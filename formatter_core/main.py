# main.py
import sys
import os
import argparse
import shutil
from .lexer import tokenize
from .syntax_check import check_syntax
from .fsm_core import format_statement_tokens
from .aligner import align_code_blocks
from .highlighter import highlight_sql

def _is_plsql_assignment(stmt_tokens):
    if not stmt_tokens: return False
    for i, tok in enumerate(stmt_tokens):
        if tok["type"] in {"comment", "space"}: continue
        if tok["type"] == "word" and not tok.get("is_keyword"):
            for j in range(i + 1, len(stmt_tokens)):
                if stmt_tokens[j]["type"] in {"comment", "space"}: continue
                if stmt_tokens[j]["text"] == ":=": return True
                return False
        return False
    return False

def _is_set_statement(stmt_tokens):
    if not stmt_tokens: return False
    for tok in stmt_tokens:
        if tok["type"] in {"comment", "space"}: continue
        if tok["is_keyword"] and tok["text"] == 'set': return True
        return False
    return False

def split_into_statements(tokens):
    statements = []
    current_stmt = []
    paren_depth = 0
    case_depth = 0
    
    for tok in tokens:
        current_stmt.append(tok)
        text = tok["text"]
        if text == '(': paren_depth += 1
        elif text == ')': paren_depth -= 1
        if tok["is_keyword"]:
            if text == 'case': case_depth += 1
            elif text == 'end': case_depth -= 1
            
        if text == ';' and paren_depth == 0 and case_depth == 0:
            statements.append(current_stmt)
            current_stmt = []
    if current_stmt: statements.append(current_stmt)
    return statements

def format_sql_file(sql_text):
    """文件格式化主逻辑 (融入硬隔离沙箱防御)"""
    all_tokens = tokenize(sql_text)
    statement_tokens_list = split_into_statements(all_tokens)
    final_output_lines = []
    n = len(statement_tokens_list)
    
    for idx, stmt_tokens in enumerate(statement_tokens_list):
        if not stmt_tokens: continue
            
        # 🚀 修复3: 真正的硬隔离容灾。如果在切分时发现语句静态校验失败，直接从切分段反推文本
        # 由于静态检查失败，这段语句不会被送入任何转换流程
        reconstructed_raw = "".join(t["text"] + (" " if t["type"] != "punct" else "") for t in stmt_tokens).strip()
        
        if not check_syntax(stmt_tokens):
            final_output_lines.append(reconstructed_raw)
            final_output_lines.append("")
            continue
            
        fsm_lines = format_statement_tokens(stmt_tokens)
        aligned_lines = align_code_blocks(fsm_lines)
        formatted_text = "\n".join(aligned_lines)
        
        post_tokens = tokenize(formatted_text)
        if not check_syntax(post_tokens):
            print("🚨 容灾防御机制生效: 局部语句格式化异常，已强制回退该段语句源码，保护运行逻辑。")
            final_output_lines.append(reconstructed_raw)
        else:
            final_output_lines.append(formatted_text)
            
        next_is_compact = (idx + 1 < n and (
            _is_set_statement(statement_tokens_list[idx + 1]) or 
            _is_plsql_assignment(statement_tokens_list[idx + 1])
        ))
        cur_is_compact = _is_set_statement(stmt_tokens) or _is_plsql_assignment(stmt_tokens)
        
        if not (cur_is_compact and next_is_compact):
            final_output_lines.append("") 

    return "\n".join(final_output_lines).strip()


def format_sql_file_html(sql_text):
    """返回格式化后的 SQL 及其语法高亮 HTML 表示。"""
    formatted = format_sql_file(sql_text)
    return highlight_sql(formatted)

# 🚀 修复 Bug K: source 下存在 'SQL文件' 中间层,输出路径需要丢弃这层。
# 例如 /root/source/SQL文件/DWD_处理逻辑/xxx/yyy.sql
#   → /root/formatted/DWD_处理逻辑/xxx/yyy_step1.sql
SOURCE_INTERMEDIATE_DIRS = {'SQL文件'}


def compute_output_paths(input_path, step_suffix="step1"):
    """
    计算格式化输出路径。

    期望的映射规则:
        /root/source/SQL文件/DWD_处理逻辑/xxx/yyy.sql
        → /root/formatted/DWD_处理逻辑/xxx/yyy_step1.sql

    步骤:
        1. 找到最右侧的 '/source/' 边界
        2. 丢弃边界后的第一个中间层目录(SOURCE_INTERMEDIATE_DIRS)
        3. 剩余路径拼到 '/formatted/' 之后
        4. 文件名追加 '_' + step_suffix(避免双下划线)
    """
    abs_input = os.path.abspath(input_path)
    normalized_input = abs_input.replace('\\', '/')

    # 找到 /source/ 边界之后的部分
    if '/source/' in normalized_input:
        before, after = normalized_input.rsplit('/source/', 1)
        # after = "SQL文件/DWD_处理逻辑/xxx/yyy.sql" 或相对路径
        after_parts = after.split('/')
        # 丢弃第一个中间层(若它在 SOURCE_INTERMEDIATE_DIRS 里)
        if after_parts and after_parts[0] in SOURCE_INTERMEDIATE_DIRS:
            after_parts = after_parts[1:]
        relative_after = '/'.join(after_parts)
        # 🚀 修复 Bug K(双下划线): 边界部分用 '/formatted/' 拼接,
        # 不再 'before + /formatted/' + after',避免前后重复。
        out_base = os.path.join(before, 'formatted', relative_after)
    elif normalized_input.startswith('source/'):
        after = normalized_input[len('source/'):]
        after_parts = after.split('/')
        if after_parts and after_parts[0] in SOURCE_INTERMEDIATE_DIRS:
            after_parts = after_parts[1:]
        relative_after = '/'.join(after_parts)
        out_base = os.path.join('formatted', relative_after)
    else:
        # 兜底安全防线:源路径不包含 source/ 时,放到同级的 formatted/ 子目录
        parent_dir = os.path.dirname(abs_input)
        base_name = os.path.basename(abs_input)
        out_base = os.path.join(parent_dir, 'formatted', base_name)

    out_base = os.path.normpath(out_base)
    out_dir = os.path.dirname(out_base)
    filename = os.path.basename(out_base)
    name_no_ext, ext = os.path.splitext(filename)

    copy_path = os.path.join(out_dir, filename)
    # 🚀 修复 Bug K(双下划线): 不论用户传 'step1' 或 '_test_v3',
    # 先 strip 掉前导下划线,再统一加一个 '_' 作为分隔符,杜绝双下划线。
    clean_suffix = step_suffix.lstrip('_')
    formatted_path = os.path.join(out_dir, f"{name_no_ext}_{clean_suffix}{ext}")

    return out_dir, copy_path, formatted_path

def process_file(input_path, step_suffix="step1"):
    if not os.path.isfile(input_path):
        print(f"❌ 文件不存在: {input_path}")
        return

    out_dir, copy_path, formatted_path = compute_output_paths(input_path, step_suffix)
    os.makedirs(out_dir, exist_ok=True)

    # 🚀 修复3: 锁死最原始的高纯度原始文本文件对象，不使用分词重建
    with open(input_path, 'r', encoding='utf-8') as f:
        raw_source_text = f.read()

    # 1. 副本备份落地 (确保 before 100% 原始字节)
    shutil.copy2(input_path, copy_path)

    # 2. 核心调度与后置防御机制
    try:
        formatted_sql = format_sql_file(raw_source_text)
    except Exception as e:
        # 🚀 极限熔断防线：如果状态机发生不可预知的 Panic 崩溃，全量回退
        print(f"🚨 顶级灾难拦截: 状态机崩溃 ({str(e)})！触发终极硬回退，原封不动保留原始 SQL 资产。")
        formatted_sql = raw_source_text

    with open(formatted_path, 'w', encoding='utf-8') as f:
        f.write(formatted_sql)

    print(f"✅ [V6.1 工业稳定版] 批处理完成: {os.path.basename(input_path)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQL 工业级格式化器 V6.1")
    parser.add_argument("file", help="需要格式化的源 SQL 文件路径")
    parser.add_argument("--step", default="step1", help="规范化文件后缀")
    args = parser.parse_args()
    process_file(args.file, args.step)