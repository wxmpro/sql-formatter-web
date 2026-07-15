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

TOP_KEYWORDS = {
    'select', 'from', 'where', 'group by', 'order by', 'having', 
    'limit', 'insert into', 'delete from', 'delete', 'update', 'left join', 
    'right join', 'inner join', 'join', 'union all', 'union', 'with', 'on',
    'create table', 'create table as', 'create temporary table', 'create temporary table as',
    'drop index', 'drop table', 'truncate table', 'set'
}

SINGLE_LINE_KEYWORDS = {'truncate table', 'truncate', 'use', 'commit', 'rollback', 'begin'}

COMPOUND_KEYWORDS = {
    'left join', 'right join', 'inner join', 'outer join', 'cross join', 
    'union all', 'group by', 'order by', 'insert into', 'partition by', 
    'truncate table', 'create table', 'drop index', 'drop table', 'create table as', 
    'create temporary table', 'create temporary table as', 'delete from'
}

# 🚀 补全数仓生态所有高频日期函数与空值判定函数，封杀大小写盲区
ALL_KEYWORDS = {
    'select', 'from', 'where', 'group', 'by', 'order', 'having', 'limit', 'insert', 'into', 
    'delete', 'update', 'left', 'right', 'inner', 'outer', 'cross', 'join', 'with', 'as', 
    'union', 'all', 'and', 'or', 'distinct', 'using', 'case', 'when', 'then', 'else', 'end',
    'set', 'on', 'in', 'exists', 'is', 'not', 'null', 'offset', 'partition', 'over', 
    'truncate', 'table', 'create', 'drop', 'index', 'use', 'commit', 'rollback', 'begin', 'declare',
    'row_number', 'rank', 'dense_rank', 'lag', 'lead', 'first_value', 'last_value', 'ntile', 
    'percent_rank', 'cume_dist', 'temporary', 'execute', 'immediate', 'if',
    'tdh_todate', 'current_timestamp', 'substring', 'nvl', 'replace', 'lpad', 'to_char',
    'sum', 'date_sub', 'trunc', 'length', 'concat', 'coalesce', 'year', 'month', 'upper',
    'cast', 'count', 'day', 'add_months',
    'asc', 'desc', 'like', 'rlike', 'regexp', 'between', 'nulls', 'first', 'last', 'true', 'false',
    'ifnull', 'isnull', 'nvl2', 'greatest', 'least', 'decode', 
    # 🌟 重点补全区
    'months_between', 'datediff', 'date_add', 'to_date', 'date_format', 'from_unixtime', 'unix_timestamp', 'current_date', 'sysdate'
}

CONTROL_KEYWORDS = {
    'and', 'or', 'in', 'exists', 'where', 'from', 'select', 'set', 'by', 'union', 'all', 
    'with', 'as', 'over', 'into', 'values', 'case', 'when', 'then', 'else', 'end', 'on', 'join', 'using', 'insert into'
}