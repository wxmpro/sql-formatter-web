# lexer.py
import re
from .constants import ALL_KEYWORDS, COMPOUND_KEYWORDS

# 🚀 修复 回归 Bug 5: 恢复针对 Hive/Spark DDL 的字符串内专用扩展关键词集合
_DQ_STRING_EXTRA_KW = {
    'if', 'stored', 'orc', 'parquet', 'textfile', 'avro', 'rcfile',
    'comment', 'location', 'external', 'partitioned', 'clustered', 'sorted',
    'buckets', 'row', 'format', 'delimited', 'fields', 'terminated', 'lines',
    'serde', 'serdeproperties', 'tblproperties',
    'replace', 'exists', 'cascade', 'restrict',
    'temporary', 'temp', 'view', 'function', 'macro',
}

SQL_LEXER_REGEX = re.compile(
    r'(?P<placeholder>\$\{[a-zA-Z_][a-zA-Z0-9_]*\})|'  # 🚀 Bug J 修复项
    r'(?P<comment>--.*?$|/\*.*?\*/)|'             
    r'(?P<string>\'(?:[^\'\\]|\\.| \'\')*\'|"(?:[^"\\]|\\.|"")*")|' 
    r'(?P<quoted_id>`[^`]*`|\[[^\]]*\])|'          
    r'(?P<op_compound>>=|<=|!=|<>|::|\|\||=>|:=|<<|>>|->>|->)|' 
    r'(?P<word>(?:[a-zA-Z_\u4e00-\u9fa5][a-zA-Z0-9_\u4e00-\u9fa5]*|\d+[a-zA-Z_\u4e00-\u9fa5][a-zA-Z0-9_\u4e00-\u9fa5]*))|' 
    r'(?P<number>\d+\.?\d*)|'                      
    r'(?P<space>\s+)|'                             
    r'(?P<punct>.)',                               
    re.DOTALL | re.MULTILINE
)

def lowercase_keywords_in_string(sql_text):
    def replace_kw(m):
        word = m.group(0)
        wl = word.lower()
        # 🚀 同步支持 _DQ_STRING_EXTRA_KW 洗白
        return wl if wl in ALL_KEYWORDS or wl in _DQ_STRING_EXTRA_KW else word
        
    def process_string(m):
        s = m.group(0)
        if s.startswith('"'):
            body = s[1:-1]
            body = re.sub(r'[a-zA-Z_][a-zA-Z0-9_]*', replace_kw, body)
            return '"' + body + '"'
        return s
    return re.sub(r'"(?:[^"\\]|\\.|"")*"', process_string, sql_text)

def extract_tokens(sql_text):
    cleaned_text = lowercase_keywords_in_string(sql_text)
    tokens = []
    for match in SQL_LEXER_REGEX.finditer(cleaned_text):
        kind = match.lastgroup
        text = match.group()
        if kind == 'space': continue
            
        is_kw = False
        if kind == 'word' and text.lower() in ALL_KEYWORDS:
            is_kw = True
            text = text.lower()
            
        if kind == 'comment' and text.startswith('--'):
            text = f"-- {text[2:].strip()}"
            
        tokens.append({"type": kind, "text": text, "is_keyword": is_kw})
    return tokens

def normalize_tokens(tokens):
    normalized = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok["is_keyword"] and i + 2 < len(tokens) and tokens[i+1]["is_keyword"] and tokens[i+2]["is_keyword"]:
            combined_3 = f"{tok['text']} {tokens[i+1]['text']} {tokens[i+2]['text']}"
            if combined_3 in COMPOUND_KEYWORDS:
                normalized.append({"type": "keyword", "text": combined_3, "is_keyword": True})
                i += 3
                continue
        if tok["is_keyword"] and i + 1 < len(tokens) and tokens[i+1]["is_keyword"]:
            combined_2 = f"{tok['text']} {tokens[i+1]['text']}"
            if combined_2 in COMPOUND_KEYWORDS:
                normalized.append({"type": "keyword", "text": combined_2, "is_keyword": True})
                i += 2
                continue
        normalized.append(tok)
        i += 1
    return normalized

def tokenize(sql_text):
    return normalize_tokens(extract_tokens(sql_text))