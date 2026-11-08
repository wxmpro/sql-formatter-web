# syntax_check.py


def check_syntax(tokens):
    """静态语法树健康度检查 (PRD 6.1)

    配对判定:
      - 括号 ( )
      - CASE ... END
      - PL/SQL BEGIN ... END  —— PL/SQL 的 END 不是 CASE 的 END, 必须分开计数,
        否则含 BEGIN...END 块的文件会被误判为语法错误而整段原样透传。
    """
    paren_depth = 0
    case_depth = 0
    plsql_depth = 0

    for tok in tokens:
        text = tok['text']
        if text == '(':
            paren_depth += 1
        elif text == ')':
            paren_depth -= 1

        if tok['is_keyword']:
            if text == 'case':
                case_depth += 1
            elif text == 'begin':
                plsql_depth += 1
            elif text == 'end':
                if plsql_depth > 0:
                    plsql_depth -= 1
                elif case_depth > 0:
                    # 只在确实有未闭合 CASE 时才配对。
                    # 多余的 end (如 PL/SQL 的 end if / end loop) 不是语法错误,
                    # 若按"配对失败"处理会让这些文件被整段原样透传, 错失规范化。
                    case_depth -= 1

        if paren_depth < 0 or case_depth < 0:
            return False

    return paren_depth == 0 and case_depth == 0
