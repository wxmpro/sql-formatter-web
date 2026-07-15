# fsm_core.py
from .constants import TOP_KEYWORDS, CONTROL_KEYWORDS, SINGLE_LINE_KEYWORDS, INDENT_SPACES, IN_LIST_THRESHOLD, Context

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

def is_subquery_lookahead(tokens, start_idx):
    for j in range(start_idx + 1, len(tokens)):
        if tokens[j]["type"] not in {'comment', 'space'}:
            return tokens[j]["text"] == 'select'
    return False

def is_complex_case(tokens, start_idx):
    when_count = 0
    logical_count = 0
    local_case_depth = 0
    for i in range(start_idx, len(tokens)):
        t = tokens[i]["text"]
        if tokens[i]["is_keyword"]:
            if t == 'case': local_case_depth += 1
            elif t == 'end':
                local_case_depth -= 1
                if local_case_depth == 0: break
            elif local_case_depth == 1:
                if t == 'when': when_count += 1
                elif t in {'and', 'or', 'select'}: logical_count += 1
    return (when_count > 1) or (logical_count > 0)

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
        self.case_indent_stack = []       
        self.case_complex_flags = []      
        
        self.context_stack = [Context.GLOBAL]
        self.indent_frame_stack = [0]     
        
        self.is_first_field = True
        self.in_set_statement = False
        self.comma_just_printed = False
        self.in_single_line_mode = False 
        self.is_after_when = False  # 🚀 Mode B 特供游标：捕获 WHEN 后的第一个条件
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
                
        if prev_tok and prev_tok.get("type") == 'placeholder' and not tok.get("is_keyword", False):
            if text not in {',', ';', ')', ']', '(', '['}:
                state.append_text(text, prepend_space=False)
                i += 1
                continue

        if tok["type"] == 'comment':
            if text.startswith('--'):
                state.append_text(text, prepend_space=True)
                state.flush_line()
            else:
                state.new_line_with_indent(extra_spaces=0)
                state.append_text(text, prepend_space=False)
                state.flush_line()
            i += 1
            continue

        # 🚀 模式 B 的核武器: 截获 WHEN 后的第一个代码块并强制爆破断行
        if state.is_after_when and tok["type"] not in {'comment', 'space'} and text not in {',', ';', 'then'}:
            state.flush_line()
            if state.scope_base() > 0: state.current_line.append(" " * state.scope_base())
            state.is_after_when = False

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
            state.flush_line()
            total = state.scope_base()
            if total > 0: state.current_line.append(" " * total)
                
            state.append_text(text, prepend_space=False)
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
                is_complex = is_complex_case(tokens, i)
                state.case_complex_flags.append(is_complex)
                
                # 🚀 Mode B: 精确捕获 CASE 在屏幕上的物理横坐标，作为后续铁幕对齐的结界
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
                is_complex = state.case_complex_flags[-1] if state.case_complex_flags else False
                if is_complex:
                    state.flush_line()
                    case_base = state.case_indent_stack[-1] if state.case_indent_stack else state.current_indent()
                    state.current_line.append(" " * (case_base + INDENT_SPACES))
                    state.append_text(text, prepend_space=False)
                    state.comma_just_printed = False 
                    
                    # 🚀 Mode B 终极变身: 压入逻辑域，并单独开辟 +2 空格的梯田基座
                    state.context_stack.append(Context.LOGICAL)
                    state.indent_frame_stack.append(case_base + INDENT_SPACES * 2)
                    state.is_after_when = True
                else:
                    state.append_text(text, prepend_space=True)
                i += 1
                continue
            elif text == 'then':
                is_complex = state.case_complex_flags[-1] if state.case_complex_flags else False
                if is_complex:
                    if state.get_context() == Context.LOGICAL: state.context_stack.pop()
                    if len(state.indent_frame_stack) > 1: state.indent_frame_stack.pop()
                    
                    state.flush_line()
                    case_base = state.case_indent_stack[-1] if state.case_indent_stack else state.current_indent()
                    state.current_line.append(" " * (case_base + INDENT_SPACES))
                    state.append_text(text, prepend_space=False)
                    state.comma_just_printed = False 
                else:
                    state.append_text(text, prepend_space=True)
                i += 1
                continue
            elif text == 'else':
                is_complex = state.case_complex_flags[-1] if state.case_complex_flags else False
                if is_complex:
                    state.flush_line()
                    case_base = state.case_indent_stack[-1] if state.case_indent_stack else state.current_indent()
                    state.current_line.append(" " * (case_base + INDENT_SPACES))
                    state.append_text(text, prepend_space=False)
                    state.comma_just_printed = False 
                else:
                    state.append_text(text, prepend_space=True)
                i += 1
                continue
            elif text == 'end':
                is_complex = state.case_complex_flags[-1] if state.case_complex_flags else False
                if is_complex:
                    state.flush_line()
                    case_base = state.case_indent_stack[-1] if state.case_indent_stack else state.current_indent()
                    if case_base > 0: state.current_line.append(" " * case_base)
                    state.append_text(text, prepend_space=False)
                else:
                    state.append_text(text, prepend_space=True)
                    
                if state.case_indent_stack: state.case_indent_stack.pop()
                if state.case_complex_flags: state.case_complex_flags.pop()
                if state.scope_stack: state.current_top_kw = state.scope_stack.pop() # 解除 case 的括号结界
                i += 1
                continue

        if tok["is_keyword"] and text in {'and', 'or'}:
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

            if next_tok and next_tok["type"] == 'comment' and next_tok["text"].startswith('--'):
                raw_c = next_tok["text"].lstrip('- ').strip()
                if len(raw_c) <= 20:
                    state.append_text(next_tok["text"], prepend_space=True)
                    state.flush_line() 
                else:
                    state.flush_line()
                    state.current_line.append(" " * state.current_indent() + next_tok["text"].strip())
                    state.flush_line()
                
                if state.get_context() == Context.FUNCTION and not is_multiline_paren:
                    state.current_line.append(" " * state.current_indent())
                    state.append_text(",", prepend_space=False)
                    state.comma_just_printed = False
                elif state.scope_stack and state.scope_stack[-1] == 'insert into' and state.paren_depth > 0:
                    spaces = state.scope_base()
                    if spaces > 0: state.current_line.append(" " * spaces)
                    state.append_text(",", prepend_space=False)
                    state.comma_just_printed = True
                else:
                    state.new_line_with_indent(extra_spaces=0)
                    state.append_text(",", prepend_space=False)
                    state.comma_just_printed = True
                    
                i += 2 
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
                if prev_tok["text"] in {'.', '(', '::'}: prepend_space = False

            should_flush_lparen = False
            is_subquery = is_subquery_lookahead(tokens, i)
            is_logic_group = is_logical_grouping(tokens, i)

            if prev_tok and prev_tok["text"] in {'exists', 'as'}: 
                should_flush_lparen = True
            elif prev_tok and prev_tok["text"] in {'in', 'values'}:
                if is_subquery or is_multiline: should_flush_lparen = True
            elif is_subquery: 
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
            
            if was_lparen_flushed or is_multiline:
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