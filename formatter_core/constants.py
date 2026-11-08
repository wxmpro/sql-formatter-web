# constants.py
from enum import Enum, auto

class Context(Enum):
    GLOBAL = auto()      # 全局最外层
    PROJECTION = auto()  # SELECT 投影区 / 字段列表
    LOGICAL = auto()     # WHERE / ON / HAVING 逻辑连接区
    FUNCTION = auto()    # 函数调用内部
    PLSQL = auto()       # DECLARE / BEGIN / END 过程控制块

INDENT_SPACES = 2
IN_LIST_THRESHOLD = 5
MAX_COMMENT_ALIGN_COL = 100

# ==================== 排版预算 (FORMAT_STYLE_SPEC §一) ====================
MAX_WIDTH = 100          # 行宽预算: 超过则条件展开
# 注: 曾经的 AND 段数阈值 / OR 一律展开规则已停用 (2026-11-08)。
# 条件是否拆分现由**宽度预算**统一决定 (见 fsm_core.analyze_case):
# 宽度够就整行, 超宽才拆。这更符合"判断语句少时放一行"的排版诉求。
MIN_ATOM_WIDTH = 4       # 孤儿行判定阈值 (有效内容下限)

# 注释排版: 注释正文 <= 此值 -> 与代码同行; 超过 -> 独立换行
# 判定只依据注释正文长度, 与代码位置无关 —— 这是幂等性的关键。
COMMENT_INLINE_MAX = 20

TOP_KEYWORDS = {
    'select', 'from', 'where', 'group by', 'order by', 'having', 
    'limit', 'insert into', 'delete from', 'delete', 'update', 'left join', 
    'right join', 'inner join', 'join', 'union all', 'union', 'with', 'on',
    'create table', 'create table as', 'create temporary table', 'create temporary table as',
    'drop index', 'drop table', 'truncate table', 'set'
}

SINGLE_LINE_KEYWORDS = {'truncate table', 'truncate', 'use', 'commit', 'rollback', 'begin'}

# 允许单独成行的关键字: 顶级子句 / 块起始 / 结构闭合。
# 这些独占一行是规格要求的正常形态, 不属于"孤儿行"(FORMAT_STYLE_SPEC 原则 P2)。
LONE_LINE_KEYWORDS = (
    {')', '(', ',', 'end', 'else', ';'}
    | set(TOP_KEYWORDS)
    | {'case', 'declare', 'begin'}
)

COMPOUND_KEYWORDS = {
    'left join', 'right join', 'inner join', 'outer join', 'cross join', 
    'union all', 'group by', 'order by', 'insert into', 'partition by', 
    'truncate table', 'create table', 'drop index', 'drop table', 'create table as', 
    'create temporary table', 'create temporary table as', 'delete from'
}

# ==================== 关键字分层 (FORMAT_STYLE_SPEC §三) ====================
# Tier A —— 语法关键字: 无条件小写。
# 只收录"几乎不可能作为列名"的词, 避免误伤。
KEYWORD_TIER_A = {
    # DML / 子句
    'select', 'from', 'where', 'group', 'by', 'order', 'having', 'limit', 'offset',
    'insert', 'into', 'delete', 'update', 'set', 'values', 'with', 'as', 'union', 'all',
    'distinct', 'using', 'on', 'in', 'exists', 'is', 'not', 'null', 'and', 'or',
    'like', 'rlike', 'regexp', 'between', 'case', 'when', 'then', 'else', 'end',
    'over', 'partition',
    # JOIN
    'join', 'left', 'right', 'inner', 'outer', 'full', 'cross', 'natural',
    # DDL
    'create', 'table', 'view', 'index', 'drop', 'alter', 'truncate', 'temporary', 'temp',
    'comment', 'primary', 'key', 'foreign', 'references', 'unique', 'constraint',
    'cascade', 'restrict',
    # 流程控制
    'use', 'commit', 'rollback', 'begin', 'declare', 'execute', 'immediate', 'if',
    'except', 'intersect', 'lateral',
    # 比较 / 排序
    'asc', 'desc', 'nulls',
    # 布尔字面量
    'true', 'false',
}

# Tier B-1 —— 函数名: 仅当紧跟 '(' 时才小写, 否则视为列名保持原样。
KEYWORD_TIER_B_FUNC = {
    'count', 'sum', 'avg', 'max', 'min',
    'abs', 'mod', 'power', 'sqrt', 'round', 'floor', 'ceil', 'ceiling', 'trunc', 'sign',
    'length', 'lengthb', 'substring', 'substr', 'split', 'trim', 'ltrim', 'rtrim',
    'replace', 'upper', 'lower', 'concat', 'coalesce',
    'nvl', 'nvl2', 'ifnull', 'isnull', 'greatest', 'least', 'decode', 'cast',
    'lpad', 'rpad', 'reverse', 'regexp_replace', 'regexp_extract',
    'to_char', 'to_date', 'to_number',
    'date_add', 'date_sub', 'datediff', 'date_format', 'months_between', 'add_months',
    'from_unixtime', 'unix_timestamp',
    'current_date', 'current_timestamp', 'current_time', 'sysdate', 'now', 'uuid', 'md5',
    'row_number', 'rank', 'dense_rank', 'lag', 'lead',
    'first_value', 'last_value', 'ntile', 'percent_rank', 'cume_dist',
    'rowid', 'rownum', 'tdh_todate',
    'year', 'month', 'day',
}

# Tier B-2 —— 类型名: 仅当处于类型位置 (前一个 token 是纯标识符) 时才小写。
KEYWORD_TIER_B_TYPE = {
    'int', 'integer', 'bigint', 'smallint', 'tinyint',
    'float', 'double', 'decimal', 'numeric',
    'string', 'varchar', 'char', 'boolean', 'binary',
    'date', 'datetime', 'timestamp',
    'array', 'map', 'struct', 'void',
}

# 兼容集合: 全部 SQL 词 (用于 is_keyword 判定与高亮回退)
ALL_KEYWORDS = KEYWORD_TIER_A | KEYWORD_TIER_B_FUNC | KEYWORD_TIER_B_TYPE

CONTROL_KEYWORDS = {
    'and', 'or', 'in', 'exists', 'where', 'from', 'select', 'set', 'by', 'union', 'all', 
    'with', 'as', 'over', 'into', 'values', 'case', 'when', 'then', 'else', 'end', 'on', 'join', 'using', 'insert into'
}