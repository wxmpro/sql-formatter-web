# highlighter.py
"""基于 lexer 输出为 SQL 文本生成语法高亮 HTML。"""

import html

from .lexer import SQL_LEXER_REGEX
from .constants import ALL_KEYWORDS


def _token_class(kind, text):
    """根据 lexer 的 token 类型返回 CSS 类名。"""
    if kind == 'word' and text.lower() in ALL_KEYWORDS:
        return 'sql-keyword'
    if kind == 'string':
        return 'sql-string'
    if kind == 'number':
        return 'sql-number'
    if kind == 'comment':
        return 'sql-comment'
    return None


def highlight_sql(sql_text):
    """把 SQL 文本转换为带高亮 span 的 HTML 片段。

    保留原始空白和换行，输出可直接放入 <pre> 或 <code> 中展示。
    """
    if not sql_text:
        return ''

    parts = []
    for match in SQL_LEXER_REGEX.finditer(sql_text):
        kind = match.lastgroup
        text = match.group()
        cls = _token_class(kind, text)
        escaped = html.escape(text, quote=False)

        if cls:
            parts.append(f'<span class="{cls}">{escaped}</span>')
        else:
            parts.append(escaped)

    return ''.join(parts)
