# aligner.py
import re
from .constants import TOP_KEYWORDS, MAX_COMMENT_ALIGN_COL


def find_comment_start(line):
    """返回行内注释的起始列; 行内无注释则返回 None。

    必须跳过字符串字面量 (单引号 / 双引号 / 反引号), 否则字符串里的 '--'
    会被误判为注释边界 —— 旧实现用 line.split(' -- ', 1) 切分, 会把
    select 'a -- b' as x 这类语句从中间劈开, 既破坏语义又破坏幂等性。
    """
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c in ("'", '"'):
            quote = c
            i += 1
            while i < n:
                if line[i] == quote:
                    if i + 1 < n and line[i + 1] == quote:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if c == '`':
            i += 1
            while i < n and line[i] != '`':
                i += 1
            i += 1
            continue
        if c == '-' and i + 1 < n and line[i + 1] == '-':
            return i
        i += 1
    return None


def align_code_blocks(lines):
    aligned_lines = []
    current_batch = []
    in_declare_block = False

    def flush_batch(batch, is_decl):
        if not batch: return []
        parsed_lines = []
        max_as_col = 0
        max_comment_col = 0
        
        for line in batch:
            stripped = line.lstrip()
            # 🚀 安全锁：保护纯注释行，防止被拆分和破坏缩进
            if stripped.startswith('--'):
                parsed_lines.append({"code": line, "as_alias": "", "comment": ""})
                continue
                
            comment_part = ""
            code_part = line
            # 精确切分代码与行尾注释 (跳过字符串字面量内的 '--')
            cpos = find_comment_start(line)
            if cpos is not None:
                code_part = line[:cpos].rstrip()
                comment_part = line[cpos:]
                
            as_match = re.search(r'\s+as\s+([a-zA-Z0-9_\u4e00-\u9fa5`\[\]\'"]+)$', code_part, re.IGNORECASE)
            as_part = ""
            if as_match:
                as_part = as_match.group(0).lstrip()
                code_part = code_part[:as_match.start()].rstrip()
                
            parsed_lines.append({"code": code_part, "as_alias": as_part, "comment": comment_part})
            if as_part: max_as_col = max(max_as_col, len(code_part))

        if is_decl:
            result = []
            for p in parsed_lines:
                assembled = p["code"]
                if p["as_alias"]: assembled += f" as {p['as_alias']}"
                if p["comment"]: assembled += f"  {p['comment'].strip()}"
                result.append(assembled)
            return result

        if any(p["as_alias"] for p in parsed_lines):
            for p in parsed_lines:
                if p["as_alias"]:
                    padding = max_as_col - len(p["code"])
                    p["code"] = p["code"] + (" " * (padding + 1)) + p["as_alias"]

        # 注: 长注释上浮已由 fsm_core 统一处理 (短备注同行 / 长注释独立成行)。
        # 此处不再二次搬动注释 —— 上浮会让 round1 与 round2 的行结构不一致, 破坏幂等性。

        for p in parsed_lines:
            if p["comment"]: max_comment_col = max(max_comment_col, len(p["code"]))

        has_multi_comments = sum(1 for p in parsed_lines if p["comment"]) >= 2
        result = []
        for p in parsed_lines:
            if has_multi_comments and p["comment"]:
                target_col = max_comment_col + 2
                if target_col > MAX_COMMENT_ALIGN_COL:
                    # 超宽: 注释独立成行, 但必须紧跟其代码行 (放在代码行之后)。
                    # 旧实现把注释行插到代码行之前 —— 那会让注释看起来属于上一个字段,
                    # 且 round1 / round2 的行序不一致, 直接破坏幂等性。
                    indent = len(p["code"]) - len(p["code"].lstrip())
                    result.append(p["code"])
                    result.append(" " * indent + p["comment"].strip())
                else:
                    padding = target_col - len(p["code"])
                    result.append(p["code"] + (" " * padding) + p["comment"])
            else:
                assembled = p["code"] + (" " + p["comment"] if p["comment"] else "")
                result.append(assembled)
        return result

    for line in lines:
        stripped = line.strip().upper()
        if stripped.startswith('DECLARE'): in_declare_block = True
        if stripped.startswith('BEGIN'): in_declare_block = False
            
        is_break = any(line.strip().startswith(kw) for kw in TOP_KEYWORDS) or line.strip() == ""
        if is_break:
            aligned_lines.extend(flush_batch(current_batch, in_declare_block))
            aligned_lines.append(line)
            current_batch = []
        else:
            current_batch.append(line)
            
    aligned_lines.extend(flush_batch(current_batch, in_declare_block))
    return aligned_lines