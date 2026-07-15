# syntax_check.py

def check_syntax(tokens):
    """静态语法树健康度检查 (PRD 6.1)"""
    paren_depth = 0
    case_depth = 0
    
    for tok in tokens:
        text = tok['text']
        if text == '(': paren_depth += 1
        elif text == ')': paren_depth -= 1
            
        if tok['is_keyword']:
            if text == 'case': case_depth += 1
            elif text == 'end': case_depth -= 1
                
        if paren_depth < 0 or case_depth < 0:
            return False
            
    return paren_depth == 0 and case_depth == 0