# highlighter.py
"""基于 lexer 输出为 SQL 文本生成语法高亮 HTML。"""

import html

from .lexer import SQL_LEXER_REGEX, classify_tokens


def _token_class(kind, text, kw_class):
    """根据 token 类型与关键字分层结果返回 CSS 类名。

    kw_class 非空才视为关键字 —— 与实际小写行为严格一致,
    避免把名为 count/length/date 的列名错误高亮成关键字。
    """
    if kw_class:
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

    matches = list(SQL_LEXER_REGEX.finditer(sql_text))

    # 先建立非空白 token 序列并做关键字分层判定
    raw = []
    for match in matches:
        if match.lastgroup == 'space':
            continue
        raw.append({
            'type': match.lastgroup,
            'text': match.group(),
            'start': match.start(),
            'end': match.end(),
        })
    classify_tokens(raw)
    class_by_pos = {(t['start'], t['end']): t.get('kw_class') for t in raw}

    parts = []
    for match in matches:
        kind = match.lastgroup
        text = match.group()
        if kind == 'space':
            parts.append(html.escape(text, quote=False))
            continue

        kw_class = class_by_pos.get((match.start(), match.end()))
        cls = _token_class(kind, text, kw_class)
        escaped = html.escape(text, quote=False)

        if cls:
            parts.append(f'<span class="{cls}">{escaped}</span>')
        else:
            parts.append(escaped)

    return ''.join(parts)
