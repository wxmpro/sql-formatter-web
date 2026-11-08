# lexer.py
import re
from .constants import (
    ALL_KEYWORDS, COMPOUND_KEYWORDS,
    KEYWORD_TIER_A, KEYWORD_TIER_B_FUNC, KEYWORD_TIER_B_TYPE,
)

SQL_LEXER_REGEX = re.compile(
    r'(?P<placeholder>\$\{[a-zA-Z_][a-zA-Z0-9_]*\})|'  # 🚀 Bug J 修复项
    r'(?P<comment>--.*?$|/\*.*?\*/)|'
    r'(?P<string>\'(?:[^\'\\]|\\.| \'\')*\'|"(?:[^"\\]|\\.|"")*")|'
    r'(?P<quoted_id>`[^`]*`|\[[^\]]*\])|'
    r'(?P<op_compound>>=|<=|!=|<>|::|\|\||=>|:=|<<|>>|->>|->)|'
    r'(?P<word>(?:[a-zA-Z_一-龥][a-zA-Z0-9_一-龥]*|\d+[a-zA-Z_一-龥][a-zA-Z0-9_一-龥]*))|'
    r'(?P<number>\d+(?:\.\d+)?)|'    r'(?P<space>\s+)|'
    r'(?P<punct>.)',
    re.DOTALL | re.MULTILINE
)


def classify_tokens(raw):
    """给 token 列表打上 is_keyword / kw_class 标签, 并按分层规则决定是否小写。

    关键字分层 (FORMAT_STYLE_SPEC §三):
      Tier A   语法关键字 -> 无条件小写
      Tier B-1 函数名   -> 仅当紧跟 '(' 时小写, 否则视为列名保持原样
      Tier B-2 类型名   -> 仅当处于类型位置 (前一个 token 是纯标识符) 时小写

    raw: [{'type','text'}, ...] (调用方需已过滤 space)
    """
    n = len(raw)
    for idx, tok in enumerate(raw):
        tok.setdefault('is_keyword', False)
        tok.setdefault('kw_class', None)
        if tok["type"] != 'word':
            continue

        wl = tok["text"].lower()
        # is_keyword 语义保持不变: 是否属于 SQL 词表 (供 FSM 结构判断使用)
        tok["is_keyword"] = wl in ALL_KEYWORDS

        kw_class = None
        if wl in KEYWORD_TIER_A:
            kw_class = 'A'
        elif wl in KEYWORD_TIER_B_FUNC:
            nxt = raw[idx + 1] if idx + 1 < n else None
            if nxt is not None and nxt["type"] == 'punct' and nxt["text"] == '(':
                kw_class = 'B_FUNC'
        elif wl in KEYWORD_TIER_B_TYPE:
            prev = raw[idx - 1] if idx > 0 else None
            if (prev is not None
                    and prev["type"] in {'word', 'quoted_id'}
                    and not prev.get('is_keyword')):
                kw_class = 'B_TYPE'

        tok["kw_class"] = kw_class
        if kw_class is not None:
            tok["text"] = wl
    return raw


def extract_tokens(sql_text):
    """切词 + 关键字分层判定。

    注意: 不对引号内内容做任何替换。双引号在 ANSI SQL 中是标识符引用,
    旧实现会把它当字符串做关键字替换 (如 "SELECT" -> "select"), 属缺陷。
    单引号字符串由 regex 的 string 分组整体捕获, 天然豁免。
    """
    raw = []
    for match in SQL_LEXER_REGEX.finditer(sql_text):
        kind = match.lastgroup
        text = match.group()
        if kind == 'space':
            continue
        if kind == 'comment' and text.startswith('--'):
            text = f"-- {text[2:].strip()}"
        raw.append({
            "type": kind,
            "text": text,
            "start": match.start(),
            "end": match.end(),
        })
    return classify_tokens(raw)


def normalize_tokens(tokens):
    normalized = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok["is_keyword"] and i + 2 < len(tokens) and tokens[i+1]["is_keyword"] and tokens[i+2]["is_keyword"]:
            combined_3 = f"{tok['text']} {tokens[i+1]['text']} {tokens[i+2]['text']}"
            if combined_3 in COMPOUND_KEYWORDS:
                normalized.append({
                    "type": "keyword", "text": combined_3, "is_keyword": True,
                    "start": tok.get("start"), "end": tokens[i + 2].get("end"),
                })
                i += 3
                continue
        if tok["is_keyword"] and i + 1 < len(tokens) and tokens[i+1]["is_keyword"]:
            combined_2 = f"{tok['text']} {tokens[i+1]['text']}"
            if combined_2 in COMPOUND_KEYWORDS:
                normalized.append({
                    "type": "keyword", "text": combined_2, "is_keyword": True,
                    "start": tok.get("start"), "end": tokens[i + 1].get("end"),
                })
                i += 2
                continue
        normalized.append(tok)
        i += 1
    return normalized


def tokenize(sql_text):
    return normalize_tokens(extract_tokens(sql_text))
