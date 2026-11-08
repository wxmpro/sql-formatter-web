# fsm_core.py
from .constants import (
    TOP_KEYWORDS, CONTROL_KEYWORDS, SINGLE_LINE_KEYWORDS, INDENT_SPACES,
    IN_LIST_THRESHOLD, MAX_WIDTH, MAX_AND_CHAIN, OR_ALWAYS_SPLIT,
    COMMENT_INLINE_MAX, Context,
)

def lookahead_comma_count(tokens, start_idx):
    comma_count = 0
    local_depth = 0
    for i in range(start_idx + 1, len(tokens)):
        tok = tokens[i]
        if tok["text"] == '(': local_depth += 1
        elif tok["text"] == ')':
            if local_depth == 0: break
            local_depth -= 1
        elif tok["text"] == ',' and local_depth == 0: comma_count += 1
    return comma_count

def _subquery_scope(tokens, open_idx):
    """分析 '(' 处的子查询: 返回 (end_idx, is_simple)。

    is_simple 判定 (FORMAT_STYLE_SPEC §四 "字段内简单子查询保持单行"):
      - 不含 where / group by / order by / having / join / union / limit / over 等子句
      - select 字段数 <= 1 (即顶层逗号数 <= 1)
    """
    depth = 0
    i = open_idx
    n = len(tokens)
    simple = True
    commas = 0
    in_select = False
    complex_kws = {
        'where', 'group by', 'order by', 'having', 'join', 'left join', 'right join',
        'inner join', 'outer join', 'full join', 'cross join', 'union', 'union all',
        'except', 'intersect', 'limit', 'over', 'qualify', 'window',
    }
    while i < n:
        tok = tokens[i]
        t = tok["text"]
        if t == '(':
            depth += 1
        elif t == ')':
            depth -= 1
            if depth == 0:
                return i, (simple and commas <= 1)
        elif depth == 1:
            if tok["is_keyword"]:
                if t == 'select':
                    in_select = True
                elif t == 'from':
                    in_select = False
                elif t in complex_kws:
                    simple = False
            elif t == ',' and in_select:
                commas += 1
        i += 1
    return None, False


def next_code_token(tokens, start_idx):
    """返回 start_idx 之后第一个非注释/非空白 token; 没有则返回 None。

    用于判定 '--' 行注释能否与代码同行: 行注释会吞掉其后的一切,
    因此其后若还有任何代码 token (包括 ';'), 注释必须独立成行。
    """
    for j in range(start_idx + 1, len(tokens)):
        if tokens[j]["type"] not in {"comment", "space"}:
            return tokens[j]
    return None


def is_subquery_lookahead(tokens, start_idx):
    for j in range(start_idx + 1, len(tokens)):
        if tokens[j]["type"] not in {'comment', 'space'}:
            return tokens[j]["text"] == 'select'
    return False

def _needs_space_between(prev, cur):
    """估算两个相邻 token 拼接时是否需要空格 (用于自然宽度计算)。"""
    pt, ct = prev["text"], cur["text"]
    if pt in {'.', '::'} or ct in {'.', '::'}:
        return False
    if pt == '(' or ct in {')', ',', ';'}:
        return False
    if pt == ',':
        return True
    wordish = {'word', 'keyword', 'number', 'placeholder', 'quoted_id'}
    return prev["type"] in wordish and cur["type"] in wordish


def _slice_width(tokens, start, end):
    """计算 token 区间 [start, end] 的自然渲染宽度 (单空格连接)。"""
    if start is None or end is None or end < start:
        return 0
    width = 0
    prev = None
    for i in range(start, end + 1):
        tok = tokens[i]
        if tok["type"] in {'comment', 'space'}:
            continue
        if prev is not None and _needs_space_between(prev, tok):
            width += 1
        width += len(tok["text"])
        prev = tok
    return width


def analyze_case(tokens, case_idx):
    """预分析一个 CASE 表达式, 产出排版布局 (FORMAT_STYLE_SPEC §二)。

    返回 dict:
        mode      'D1' (整块单行) | 'MULTI' (每分支一行)
        branches  分支列表, 每个分支含 cond/val 区间、and/or 计数、宽度、split 标记
        when_map  {when_token_index: branch} 供渲染期定位分支

    计数口径 (规格 §2.2):
        or_n  = 顶层 (不在括号内) 的 OR 数量
        and_n = 顶层 OR 切分后各 OR 段内 AND 数量的最大值
        width = len('when ' + cond + ' then ' + val) 的自然渲染宽度
    """
    branches = []
    cur = None
    case_depth = 0
    paren_depth = 0
    n = len(tokens)
    i = case_idx

    while i < n:
        tok = tokens[i]
        text = tok["text"]

        if text == '(':
            paren_depth += 1
        elif text == ')':
            paren_depth -= 1

        if tok["is_keyword"]:
            if text == 'case':
                case_depth += 1
            elif text == 'end':
                if cur is not None:
                    cur['val_end'] = i - 1
                    cur = None
                case_depth -= 1
                if case_depth == 0:
                    break
            elif case_depth == 1 and paren_depth == 0:
                if text in ('when', 'else'):
                    if cur is not None:
                        cur['val_end'] = i - 1
                    if text == 'when':
                        cur = {
                            'kind': 'when', 'when_idx': i, 'cond_start': i + 1,
                            'cond_end': None, 'then_idx': None, 'val_start': None,
                            'val_end': None, 'and_positions': [], 'or_count': 0,
                            'and_count': 0, 'has_comment': False, 'split': False,
                        }
                    else:
                        cur = {
                            'kind': 'else', 'else_idx': i, 'val_start': i + 1,
                            'val_end': None, 'and_positions': [], 'or_count': 0,
                            'and_count': 0, 'has_comment': False, 'split': False,
                        }
                    branches.append(cur)
                elif text == 'then' and cur is not None and cur['kind'] == 'when':
                    cur['cond_end'] = i - 1
                    cur['then_idx'] = i
                    cur['val_start'] = i + 1
                elif text in ('and', 'or') and cur is not None and cur.get('then_idx') is None:
                    # 只统计条件区 (then 之前) 的顶层逻辑运算符
                    if text == 'or':
                        cur['or_count'] += 1
                    else:
                        cur['and_count'] += 1
                        cur['and_positions'].append(i)

        if cur is not None and tok["type"] == 'comment':
            # 硬约束 H1: 分支内出现注释时必须强制拆行, 防 -- 吞掉 then/else/end
            cur['has_comment'] = True

        i += 1

    # 计算各分支的自然宽度
    for b in branches:
        if b['kind'] == 'when':
            cond_w = _slice_width(tokens, b['cond_start'], b['cond_end'])
            val_w = _slice_width(tokens, b['val_start'], b['val_end'])
            b['width'] = len('when ') + cond_w + len(' then ') + val_w
        else:
            val_w = _slice_width(tokens, b['val_start'], b['val_end'])
            b['width'] = len('else ') + val_w

    # 档位判定
    # 注意: D1 的"单分支"指 WHEN 分支数 == 1 (else 属于该分支的一部分, 不单独计数)
    when_branches = [b for b in branches if b['kind'] == 'when']
    if (len(when_branches) == 1
            and not when_branches[0]['has_comment']
            and when_branches[0]['width'] <= MAX_WIDTH):
        mode = 'D1'
    else:
        mode = 'MULTI'
        for b in branches:
            b['split'] = (
                b['has_comment']
                or (OR_ALWAYS_SPLIT and b['or_count'] > 0)
                or b['and_count'] >= MAX_AND_CHAIN
                or b['width'] > MAX_WIDTH
            )

    return {
        'mode': mode,
        'branches': branches,
        'when_map': {b['when_idx']: b for b in branches if b['kind'] == 'when'},
    }

def is_logical_grouping(tokens, start_idx):
    local_depth = 0
    for i in range(start_idx + 1, len(tokens)):
        t = tokens[i]["text"]
        if t == '(': local_depth += 1
        elif t == ')':
            if local_depth == 0: break
            local_depth -= 1
        elif local_depth == 0 and t in {'and', 'or'}:
            return True
    return False

class FormatState:
    def __init__(self):
        self.paren_depth = 0
        self.current_top_kw = None
        self.scope_stack = []             
        self.paren_indent_stack = []      
        self.paren_reasons = []           
        self.paren_multiline_flags = []
        self.paren_flush_lparen_flags = []
        self.simple_subq_flags = []      # 每个括号是否为"字段内简单子查询"
        self.simple_subq_depth = 0       # 当前嵌套的简单子查询层数
        self.case_indent_stack = []
        self.case_layouts = []          # 每个 CASE 的排版布局 (analyze_case 产出)
        self.case_frames = []           # 每个 WHEN 分支的渲染帧 {base, mode, case_level}

        self.context_stack = [Context.GLOBAL]
        self.indent_frame_stack = [0]

        self.is_first_field = True
        self.in_set_statement = False
        self.comma_just_printed = False
        self.in_single_line_mode = False
        self.output_lines = []
        self.current_line = []

    def get_context(self):
        return self.context_stack[-1] if self.context_stack else Context.GLOBAL

    def scope_base(self):
        # 🚀 彻底剥离 case 的粗暴叠加，交由栈自身精细管理层级
        return self.indent_frame_stack[-1] if self.indent_frame_stack else 0

    def current_indent(self):
        base = self.scope_base()
        if self.current_top_kw:
            return base + INDENT_SPACES
        return base

    def flush_line(self):
        if self.current_line:
            line_str = "".join(self.current_line).rstrip()
            if line_str: 
                self.output_lines.append(line_str)
            self.current_line = []
            self.comma_just_printed = False

    def append_text(self, text, prepend_space=True):
        if self.current_line and prepend_space and not self.current_line[-1].endswith(" "):
            self.current_line.append(" ")
        self.current_line.append(text)
        self.comma_just_printed = False

    def new_line_with_indent(self, extra_spaces=0):
        self.flush_line()
        total = self.current_indent() + extra_spaces
        if total > 0: self.current_line.append(" " * total)

    def handle_first_field(self):
        if not self.is_first_field: return
        # 简单子查询内部保持单行
        if self.simple_subq_depth > 0:
            self.is_first_field = False
            return
        effective_kw = self.current_top_kw
        if effective_kw is None and self.scope_stack:
            for kw in reversed(self.scope_stack):
                if kw in {'select', 'group by', 'order by', 'insert into', 'set', 'from', 'where', 'on', 'having'}:
                    effective_kw = kw
                    break
                    
        if effective_kw in {'select', 'group by', 'order by'}:
            self.new_line_with_indent(extra_spaces=1) 
        elif effective_kw in {'from', 'where', 'having', 'set'}:
            self.new_line_with_indent(extra_spaces=0)
        elif effective_kw == 'on':
            pass
        elif effective_kw == 'insert into':
            if self.paren_depth > 0:
                self.flush_line()
                spaces = self.scope_base() + 1
                if spaces > 0: self.current_line.append(" " * spaces)
            else:
                self.new_line_with_indent(extra_spaces=0)
        self.is_first_field = False


def format_statement_tokens(tokens):
    state = FormatState()
    i = 0
    
    while i < len(tokens):
        tok = tokens[i]
        text = tok["text"]
        prev_tok = tokens[i-1] if i > 0 else None
        next_tok = tokens[i+1] if i + 1 < len(tokens) else None
        
        if text in {'.', '::'} or (prev_tok and prev_tok["text"] in {'.', '::'}):
            state.append_text(text, prepend_space=False)
            i += 1
            continue

        if tok.get("type") == 'placeholder' and prev_tok:
            is_valid_word = prev_tok.get("type") in {'word', 'quoted_id'} and prev_tok.get("text") not in CONTROL_KEYWORDS
            is_punct_connector = prev_tok.get("text") in {'_', '.'}
            if is_valid_word or is_punct_connector:
                state.append_text(text, prepend_space=False)
                i += 1
                continue
                
        if (prev_tok and prev_tok.get("type") == 'placeholder'
                and not tok.get("is_keyword", False)
                and tok["type"] != 'comment'):
            if text not in {',', ';', ')', ']', '(', '['}:
                state.append_text(text, prepend_space=False)
                i += 1
                continue

        if tok["type"] == 'comment':
            # 统一注释排版 (FORMAT_STYLE_SPEC §四):
            #   短字段备注 (正文 <= COMMENT_INLINE_MAX) -> 与代码同行
            #   解释性 / 字多                        -> 独立换行
            # 判定只依据注释正文长度, 与注释在代码中的位置无关,
            # 这是格式化幂等性的关键 (旧实现在 ',' 分支里有第二套判定, 两条路径不一致)。
            if text.startswith('--'):
                body = text.lstrip('-').strip()
                # '--' 行注释会吞掉其后的一切: 其后若还有代码 token (含 ';'),
                # 注释必须独立成行, 否则会吞掉分号或后续语句。
                trailing = next_code_token(tokens, i)
                if len(body) <= COMMENT_INLINE_MAX and trailing is None:
                    # 短备注: 与当前行同行
                    state.append_text(text, prepend_space=True)
                    state.flush_line()
                else:
                    # 长注释: 独立成行, 缩进沿用当前层级
                    state.flush_line()
                    indent = state.current_indent()
                    if indent > 0:
                        state.current_line.append(" " * indent)
                    state.append_text(text, prepend_space=False)
                    state.flush_line()
            else:
                # 块注释整块输出 (保留内部换行)。
                # 注意: 不能逐行拆散 —— 块注释内的空行会丢失, 导致 round1/round2 不一致。
                state.new_line_with_indent(extra_spaces=0)
                state.append_text(text, prepend_space=False)
                state.flush_line()
            i += 1
            continue

        if tok["is_keyword"] and text == 'declare' and state.paren_depth == 0:
            state.flush_line()
            state.context_stack.append(Context.PLSQL)
            state.append_text(text, prepend_space=False)
            state.flush_line()
            i += 1
            continue
            
        if tok["is_keyword"] and text == 'begin' and state.get_context() == Context.PLSQL:
            state.flush_line()
            if len(state.context_stack) > 1: state.context_stack.pop()
            state.append_text(text, prepend_space=False)
            state.flush_line()
            i += 1
            continue

        if tok["is_keyword"] and text in SINGLE_LINE_KEYWORDS and state.paren_depth == 0:
            state.flush_line()
            state.in_single_line_mode = True
            state.append_text(text, prepend_space=False)
            i += 1
            continue

        if state.in_single_line_mode:
            space_needed = not (text in {';', ',', '='} or (prev_tok and prev_tok["text"] in {'='}))
            state.append_text(text, prepend_space=space_needed)
            if text == ';':
                state.flush_line()
                state.in_single_line_mode = False
            i += 1
            continue

        if tok["is_keyword"] and text == 'set' and state.paren_depth == 0:
            is_env_set = True
            for prev_i in range(i-1, -1, -1):
                if tokens[prev_i]["type"] not in {'comment', 'space'}:
                    is_env_set = False
                    break
            if is_env_set:
                state.flush_line()
                state.in_set_statement = True
                state.append_text(text, prepend_space=False)
                i += 1
                continue

        if state.in_set_statement:
            if text in {'=', ';'}: state.append_text(text, prepend_space=False)
            elif prev_tok and prev_tok["text"] == '=': state.append_text(text, prepend_space=False)
            else: state.append_text(text, prepend_space=True)
            if text == ';':
                state.flush_line()
                state.in_set_statement = False
            i += 1
            continue

        is_top_kw = tok["is_keyword"] and text in TOP_KEYWORDS
        in_over_clause = state.paren_reasons and state.paren_reasons[-1] == 'over'
        
        if (in_over_clause or state.get_context() == Context.FUNCTION) and text in {'order by', 'partition by', 'group by', 'on'}:
            is_top_kw = False

        if is_top_kw:
            # 简单子查询内部保持单行, 不换行
            if state.simple_subq_depth == 0:
                state.flush_line()
                total = state.scope_base()
                if total > 0: state.current_line.append(" " * total)
                state.append_text(text, prepend_space=False)
            else:
                # 单行路径: '(' 后不留空格, 其余关键字之间留一个空格
                need_space = True
                if state.current_line and state.current_line[-1].endswith('('):
                    need_space = False
                state.append_text(text, prepend_space=need_space)

            state.current_top_kw = text
            state.is_first_field = True
            
            if text in {'select', 'group by', 'order by'}: state.context_stack[-1] = Context.PROJECTION
            elif text in {'where', 'on', 'having'}: state.context_stack[-1] = Context.LOGICAL
            else: state.context_stack[-1] = Context.GLOBAL
                
            i += 1
            continue

        if state.is_first_field and text not in {',', ';', ')', 'distinct'}:
            if tok["type"] != 'comment' and text not in {'declare', 'begin', 'end', 'set'}:
                state.handle_first_field()

        if tok["is_keyword"]:
            if text == 'case':
                # 预分析整个 CASE 表达式, 决定 D1(整块单行) / MULTI(每分支一行)
                layout = analyze_case(tokens, i)
                state.case_layouts.append(layout)

                # 精确捕获 CASE 在屏幕上的物理横坐标，作为后续铁幕对齐的结界
                if not state.current_line:
                    case_col = state.current_indent()
                else:
                    case_col = len("".join(state.current_line))
                    if not state.comma_just_printed and not "".join(state.current_line).endswith(" "):
                        case_col += 1
                state.case_indent_stack.append(case_col)

                # 将 case 视同括号，打断并封存顶级关键字，防止作用域污染
                state.scope_stack.append(state.current_top_kw)
                state.current_top_kw = None

                state.append_text(text, prepend_space=not state.comma_just_printed)
                i += 1
                continue
            elif text == 'when':
                layout = state.case_layouts[-1] if state.case_layouts else None
                if layout and layout['mode'] == 'MULTI':
                    branch = layout['when_map'].get(i)
                    case_base = state.case_indent_stack[-1] if state.case_indent_stack else state.current_indent()
                    when_base = case_base + INDENT_SPACES

                    state.flush_line()
                    if when_base > 0:
                        state.current_line.append(" " * when_base)
                    state.append_text(text, prepend_space=False)
                    state.comma_just_printed = False

                    mode = 'split' if (branch and branch.get('split')) else 'inline'
                    state.case_frames.append({
                        'base': when_base,
                        'mode': mode,
                        'case_level': len(state.case_layouts),
                    })

                    # 压入逻辑域, 条件区换行时的基准缩进
                    state.context_stack.append(Context.LOGICAL)
                    state.indent_frame_stack.append(when_base + INDENT_SPACES)
                else:
                    # D1: 整块单行, 条件不换行
                    state.append_text(text, prepend_space=True)
                    state.case_frames.append({
                        'base': 0, 'mode': 'inline', 'case_level': len(state.case_layouts),
                    })
                i += 1
                continue
            elif text == 'then':
                layout = state.case_layouts[-1] if state.case_layouts else None
                frame = state.case_frames[-1] if state.case_frames else None
                if layout and layout['mode'] == 'MULTI':
                    if frame and frame['mode'] == 'split':
                        # 条件已展开: then 回到 when 的缩进基线
                        state.flush_line()
                        if frame['base'] > 0:
                            state.current_line.append(" " * frame['base'])
                        state.append_text(text, prepend_space=False)
                    else:
                        state.append_text(text, prepend_space=True)
                    state.comma_just_printed = False

                    if state.get_context() == Context.LOGICAL:
                        state.context_stack.pop()
                    if len(state.indent_frame_stack) > 1:
                        state.indent_frame_stack.pop()
                else:
                    state.append_text(text, prepend_space=True)
                if state.case_frames:
                    state.case_frames.pop()
                i += 1
                continue
            elif text == 'else':
                layout = state.case_layouts[-1] if state.case_layouts else None
                if layout and layout['mode'] == 'MULTI':
                    case_base = state.case_indent_stack[-1] if state.case_indent_stack else state.current_indent()
                    state.flush_line()
                    if case_base + INDENT_SPACES > 0:
                        state.current_line.append(" " * (case_base + INDENT_SPACES))
                    state.append_text(text, prepend_space=False)
                    state.comma_just_printed = False
                else:
                    state.append_text(text, prepend_space=True)
                i += 1
                continue
            elif text == 'end':
                layout = state.case_layouts[-1] if state.case_layouts else None
                if layout and layout['mode'] == 'MULTI':
                    case_base = state.case_indent_stack[-1] if state.case_indent_stack else state.current_indent()
                    state.flush_line()
                    if case_base > 0:
                        state.current_line.append(" " * case_base)
                    state.append_text(text, prepend_space=False)
                else:
                    state.append_text(text, prepend_space=True)

                # 清理可能残留的分支帧 (语法异常导致缺少 then 时)
                level = len(state.case_layouts)
                while state.case_frames and state.case_frames[-1]['case_level'] >= level:
                    state.case_frames.pop()
                if state.case_layouts:
                    state.case_layouts.pop()
                if state.case_indent_stack:
                    state.case_indent_stack.pop()
                if state.scope_stack:
                    state.current_top_kw = state.scope_stack.pop()  # 解除 case 的括号结界
                i += 1
                continue

        if tok["is_keyword"] and text in {'and', 'or'}:
            # CASE 分支条件区: 展开与否由 analyze_case 预判决定 (FORMAT_STYLE_SPEC §2.3)
            if state.case_frames and state.paren_depth == 0:
                frame = state.case_frames[-1]
                if frame['mode'] == 'split':
                    state.flush_line()
                    if frame['base'] + INDENT_SPACES > 0:
                        state.current_line.append(" " * (frame['base'] + INDENT_SPACES))
                    state.append_text(text, prepend_space=False)
                else:
                    state.append_text(text, prepend_space=True)
                i += 1
                continue

            if state.get_context() == Context.LOGICAL and not (state.paren_reasons and state.paren_reasons[-1] == 'over'):
                state.new_line_with_indent(extra_spaces=0)
                state.append_text(text, prepend_space=False)
                i += 1
                continue

        if tok["is_keyword"] and text == 'distinct' and state.get_context() == Context.PROJECTION:
            state.new_line_with_indent(extra_spaces=0)
            state.append_text(text, prepend_space=False)
            i += 1
            continue

        if text == ',':
            if state.paren_reasons and state.paren_reasons[-1] == 'over':
                state.append_text(",", prepend_space=False)
                state.comma_just_printed = False
                i += 1
                continue
                
            is_multiline_paren = state.paren_multiline_flags and state.paren_multiline_flags[-1]
            
            if state.paren_depth > 0 and not is_multiline_paren and state.get_context() == Context.GLOBAL:
                state.append_text(",", prepend_space=False)
                state.comma_just_printed = False
                i += 1
                continue

                
            if state.get_context() == Context.FUNCTION and not is_multiline_paren:
                state.append_text(",", prepend_space=False)
                state.comma_just_printed = False
            elif state.scope_stack and state.scope_stack[-1] == 'insert into' and state.paren_depth > 0:
                state.flush_line()
                spaces = state.scope_base()
                if spaces > 0: state.current_line.append(" " * spaces)
                state.append_text(",", prepend_space=False)
                state.comma_just_printed = True
            else:
                state.new_line_with_indent(extra_spaces=0)
                state.append_text(",", prepend_space=False)
                state.comma_just_printed = True
            i += 1
            continue

        if text == '(':
            reason = prev_tok["text"] if prev_tok else None
            state.paren_reasons.append(reason)
            
            comma_count = lookahead_comma_count(tokens, i)
            is_multiline = comma_count >= IN_LIST_THRESHOLD 
            
            if prev_tok and prev_tok["text"] == 'over':
                is_multiline = False

            state.paren_multiline_flags.append(is_multiline)
            
            prepend_space = True
            if prev_tok:
                if prev_tok["type"] in {'word', 'keyword', 'placeholder'} and prev_tok["text"] not in CONTROL_KEYWORDS: prepend_space = False
                if prev_tok["text"] in {'.', '(', '::', ','}: prepend_space = False

            should_flush_lparen = False
            is_subquery = is_subquery_lookahead(tokens, i)
            is_logic_group = is_logical_grouping(tokens, i)

            # 字段位置的简单子查询: 整体保持单行 (FORMAT_STYLE_SPEC §四)
            is_simple_subq = False
            if is_subquery and state.get_context() == Context.PROJECTION:
                end_idx, simple = _subquery_scope(tokens, i)
                if simple and end_idx is not None:
                    if _slice_width(tokens, i, end_idx) <= MAX_WIDTH:
                        is_simple_subq = True

            if prev_tok and prev_tok["text"] in {'exists', 'as'}:
                should_flush_lparen = True
            elif prev_tok and prev_tok["text"] in {'in', 'values'}:
                if is_subquery or is_multiline: should_flush_lparen = True
            elif is_subquery and not is_simple_subq:
                should_flush_lparen = True
            elif state.current_top_kw in {'insert into', 'delete from', 'update'} and state.paren_depth == 0:
                if prev_tok and prev_tok["text"] == 'partition':
                    should_flush_lparen = False
                else:
                    should_flush_lparen = True
            elif state.get_context() == Context.LOGICAL and is_logic_group:
                should_flush_lparen = True

            is_func = prev_tok and prev_tok["type"] in {'word', 'quoted_id'} and prev_tok["text"] not in CONTROL_KEYWORDS
            if should_flush_lparen:
                is_func = False
                
            if is_func:
                state.context_stack.append(Context.FUNCTION)
            elif state.get_context() == Context.LOGICAL and is_logic_group:
                state.context_stack.append(Context.LOGICAL)
            else:
                state.context_stack.append(Context.GLOBAL)

            state.paren_flush_lparen_flags.append(should_flush_lparen)

            if should_flush_lparen:
                if state.current_top_kw in {'with', 'insert into', 'delete from', 'update', 'union all', 'union'} or (state.current_top_kw and 'join' in state.current_top_kw):
                    paren_spaces = state.scope_base()
                elif state.get_context() == Context.LOGICAL and is_logic_group:
                    paren_spaces = state.current_indent() 
                elif prev_tok and prev_tok["text"] == 'when':
                    paren_spaces = state.current_indent() + INDENT_SPACES
                else:
                    paren_spaces = state.current_indent()
                    
                current_env_indent = paren_spaces + INDENT_SPACES
                    
                state.flush_line()
                if paren_spaces > 0: state.current_line.append(" " * paren_spaces)
                prepend_space = False
            else:
                paren_spaces = len("".join(state.current_line)) - len("".join(state.current_line).lstrip())
                current_env_indent = paren_spaces + INDENT_SPACES 
                
            state.indent_frame_stack.append(current_env_indent)
                
            state.append_text(text, prepend_space=prepend_space)
            state.paren_indent_stack.append(paren_spaces)
            state.scope_stack.append(state.current_top_kw)
            state.current_top_kw = None
            state.paren_depth += 1
            state.simple_subq_flags.append(is_simple_subq)
            if is_simple_subq:
                state.simple_subq_depth += 1
            
            if (is_multiline and reason in {'in', 'values'}) or (state.get_context() == Context.LOGICAL and is_logic_group):
                state.flush_line()
                first_indent = current_env_indent
                if reason == 'insert into':
                    first_indent = paren_spaces + 1
                elif reason in {'in', 'values'}:
                    first_indent = current_env_indent + 1 
                state.current_line.append(" " * first_indent)
                state.is_first_field = False
            
            # 🚀 物理结构解耦: 解决 partition 屏蔽首字段识别的绝境，只要是 flushed paren 就放行
            if should_flush_lparen and state.scope_stack and state.scope_stack[-1] == 'insert into':
                state.is_first_field = True
            elif (prev_tok and prev_tok["type"] in {'word', 'quoted_id'} and not prev_tok.get("is_keyword", False) and state.scope_stack and state.scope_stack[-1] == 'insert into'):
                state.is_first_field = True
                
            i += 1
            continue

        if text == ')':
            state.paren_depth -= 1
            if state.paren_reasons: state.paren_reasons.pop()
            if state.scope_stack: state.current_top_kw = state.scope_stack.pop()
            if len(state.context_stack) > 1: state.context_stack.pop()
            
            if len(state.indent_frame_stack) > 1: state.indent_frame_stack.pop()
            
            is_multiline = state.paren_multiline_flags.pop() if state.paren_multiline_flags else False
            target_spaces = state.paren_indent_stack.pop() if state.paren_indent_stack else state.scope_base()
            was_lparen_flushed = state.paren_flush_lparen_flags.pop() if state.paren_flush_lparen_flags else False
            is_simple_subq = state.simple_subq_flags.pop() if state.simple_subq_flags else False
            if is_simple_subq:
                state.simple_subq_depth = max(0, state.simple_subq_depth - 1)

            if (was_lparen_flushed or is_multiline) and not is_simple_subq:
                state.flush_line()
                if target_spaces > 0: state.current_line.append(" " * target_spaces)
                
            state.append_text(text, prepend_space=False)
            i += 1
            continue

        if text == ';':
            state.append_text(text, prepend_space=False)
            state.flush_line()
            state.current_top_kw = None
            state.paren_depth = 0
            
            state.context_stack = [Context.GLOBAL]
            state.indent_frame_stack = [0]
            state.case_indent_stack = []
            state.case_layouts = []
            state.case_frames = []
            
            i += 1
            continue

        space_needed = not state.comma_just_printed
        if prev_tok and prev_tok["text"] in {'(', '['}: space_needed = False
        if text in {']', '}'}: space_needed = False
        if text == '[': space_needed = False
            
        state.append_text(text, prepend_space=space_needed)
        i += 1

    state.flush_line()
    return state.output_lines