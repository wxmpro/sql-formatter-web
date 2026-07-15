# aligner.py
import re
from .constants import TOP_KEYWORDS, MAX_COMMENT_ALIGN_COL

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
            if ' -- ' in line:
                parts = line.split(' -- ', 1)
                code_part = parts[0].rstrip()
                comment_part = ' -- ' + parts[1]
                
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

        # 🚀 规则 4 落地：超长注释智能上浮漂移 (仅处理非纯注释行的尾部注释)
        shifted_lines = []
        for p in parsed_lines:
            if p["comment"]:
                raw_c = p["comment"].replace(' -- ', '', 1).strip()
                if len(raw_c) > 20: 
                    indent = len(p["code"]) - len(p["code"].lstrip())
                    shifted_lines.append({"code": " " * indent + p["comment"].strip(), "as_alias": "", "comment": ""})
                    p["comment"] = "" 
            shifted_lines.append(p)
            
        parsed_lines = shifted_lines

        for p in parsed_lines:
            if p["comment"]: max_comment_col = max(max_comment_col, len(p["code"]))

        has_multi_comments = sum(1 for p in parsed_lines if p["comment"]) >= 2
        result = []
        for p in parsed_lines:
            if has_multi_comments and p["comment"]:
                target_col = max_comment_col + 2
                if target_col > MAX_COMMENT_ALIGN_COL:
                    indent = len(p["code"]) - len(p["code"].lstrip())
                    result.append(" " * indent + p["comment"].strip())
                    result.append(p["code"])
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