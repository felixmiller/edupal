import edupal
from pyeda.inter import expr as pyeda_expr, exprvar


def test_cdnf_to_latex():
    # ones at positions 2, 4, 5
    assert edupal.cdnf_to_latex('00101100') == r'\Sigma(2, 4, 5)'


def test_ccnf_to_latex():
    # zeros at positions 0, 1, 3, 6, 7
    assert edupal.ccnf_to_latex('00101100') == r'\Pi(0, 1, 3, 6, 7)'


def test_cdnf_all_ones():
    assert edupal.cdnf_to_latex('11') == r'\Sigma(0, 1)'


def test_ccnf_all_ones():
    assert edupal.ccnf_to_latex('11') == r'\Pi()'


def test_latex_func_header():
    assert edupal.latex_func_header('y0', ['x2', 'x1', 'x0']) == r'y_{0}(x_{2}, x_{1}, x_{0})'


def test_latex_func_header_no_subscript():
    assert edupal.latex_func_header('f', ['x0']) == r'f(x_{0})'


def test_truth_table_to_latex_structure():
    latex = edupal.truth_table_to_latex([0, 1, 1, 0])
    assert r'\begin{tabular}' in latex
    assert r'\hline' in latex
    assert 'Dec' in latex


def test_truth_table_to_latex_row_count():
    # 4 input combinations → 4 data rows
    latex = edupal.truth_table_to_latex([0, 1, 1, 0])
    # Each row ends with \\
    assert latex.count(r'\\') >= 4


def test_tt_str_to_latex_str_cdnf():
    result = edupal.tt_str_to_latex_str_cdnf('00101100', ['x2','x1','x0'], 'y')
    assert '=' in result
    assert r'\Sigma' in result


def test_tt_str_min_to_latex_str_constant_one():
    # All-ones truth table for 2 inputs (4 rows): minimized expression should be 1
    result = edupal.tt_str_min_to_latex_str('1111', ['x1', 'x0'], 'y')
    assert '=' in result
    assert '1' in result


def test_tt_str_min_to_latex_str_and():
    # "1000" for 2 inputs (MSB-first): only row 00 (x1=0, x0=0) is 1 → ~x1 AND ~x0
    result = edupal.tt_str_min_to_latex_str('1000', ['x1', 'x0'], 'y')
    assert result == r'y(x_{0}, x_{1})=\olsi{x_{1}}\olsi{x_{0}}'


def test_expr_to_cdnf_latex_and():
    # x0 AND x1, vlist LSB-first ['x0','x1']:
    # i=0: x0=0,x1=0 → 0 | i=1: x0=1,x1=0 → 0 | i=2: x0=0,x1=1 → 0 | i=3: x0=1,x1=1 → 1
    x0, x1 = exprvar('x0'), exprvar('x1')
    result = edupal.expr_to_cdnf_latex(x0 & x1, ['x0', 'x1'], 'y')
    assert result == r'y(x_{1}, x_{0})=\Sigma(3)'


def test_expr_to_cdnf_latex_reversed_vlist():
    # x0 AND ~x1, vlist LSB-first ['x1','x0'] (x1 i LSB, x0 is MSB):
    # i=0: x1=0,x0=0 → 0 | i=1: x1=1,x0=0 → 0 | i=2: x1=0,x0=1 → 1 | i=3: x1=1,x0=1 → 0
    x0, x1 = exprvar('x0'), exprvar('x1')
    result = edupal.expr_to_cdnf_latex(x0 & ~x1, ['x1', 'x0'], 'y')
    assert result == r'y(x_{0}, x_{1})=\Sigma(2)'


def test_expr_to_cdnf_latex_or():
    # x0 OR x1: minterms at i=1,2,3
    x0, x1 = exprvar('x0'), exprvar('x1')
    result = edupal.expr_to_cdnf_latex(x0 | x1, ['x0', 'x1'], 'y')
    assert result == r'y(x_{1}, x_{0})=\Sigma(1,2,3)'


def test_expr_to_ccnf_latex_and():
    # x0 AND x1: maxterms at i=0,1,2
    x0, x1 = exprvar('x0'), exprvar('x1')
    result = edupal.expr_to_ccnf_latex(x0 & x1, ['x0', 'x1'], 'y')
    assert result == r'y(x_{1}, x_{0})=\Pi(0,1,2)'


def test_expr_to_ccnf_latex_or():
    # x0 OR x1: maxterm only at i=0
    x0, x1 = exprvar('x0'), exprvar('x1')
    result = edupal.expr_to_ccnf_latex(x0 | x1, ['x0', 'x1'], 'y')
    assert result == r'y(x_{1}, x_{0})=\Pi(0)'


# --- expr_to_latex_expr ---

def test_expr_to_latex_expr_variable():
    assert edupal.expr_to_latex_expr(exprvar('x0')) == 'x_{0}'


def test_expr_to_latex_expr_complement():
    assert edupal.expr_to_latex_expr(~exprvar('x0')) == r'\olsi{x_{0}}'


def test_expr_to_latex_expr_constant_one():
    assert edupal.expr_to_latex_expr(pyeda_expr('1')) == '1'


def test_expr_to_latex_expr_constant_zero():
    assert edupal.expr_to_latex_expr(pyeda_expr('0')) == '0'


def test_expr_to_latex_expr_and_two_literals():
    # All literals: \land omitted, sorted reverse (x1 > x0)
    x0, x1 = exprvar('x0'), exprvar('x1')
    assert edupal.expr_to_latex_expr(x0 & x1) == 'x_{1}x_{0}'


def test_expr_to_latex_expr_and_three_literals():
    # Pyeda builds (x0 & x1) & x2; inner AND produces a non-literal child → \land used
    x0, x1, x2 = exprvar('x0'), exprvar('x1'), exprvar('x2')
    assert edupal.expr_to_latex_expr(x0 & x1 & x2) == r'x_{1}x_{0} \land x_{2}'


def test_expr_to_latex_expr_and_with_complement():
    # sort key of ~x1 is 'x1', of x0 is 'x0'; reverse → ~x1 first
    x0, x1 = exprvar('x0'), exprvar('x1')
    assert edupal.expr_to_latex_expr(~x1 & x0) == r'\olsi{x_{1}}x_{0}'


def test_expr_to_latex_expr_or_literals_toplevel():
    # Top-level OR: no outer parens; sorted reverse
    x0, x1 = exprvar('x0'), exprvar('x1')
    assert edupal.expr_to_latex_expr(x0 | x1) == r'x_{1} \lor x_{0}'


def test_expr_to_latex_expr_or_gets_parens_when_nested():
    # OR inside AND must be parenthesised; AND uses \land for mixed literal/non-literal children
    x0, x1, x2 = exprvar('x0'), exprvar('x1'), exprvar('x2')
    assert edupal.expr_to_latex_expr(x0 & (x1 | x2)) == r'x_{0} \land (x_{2} \lor x_{1})'


def test_expr_to_latex_expr_sop():
    # Sum of products: two AND terms OR'd at top level (no outer parens)
    # x0&x1 and x2&x3 share no variables so pyeda cannot factor further
    x0, x1, x2, x3 = exprvar('x0'), exprvar('x1'), exprvar('x2'), exprvar('x3')
    assert edupal.expr_to_latex_expr((x0 & x1) | (x2 & x3)) == r'x_{1}x_{0} \lor x_{3}x_{2}'


# --- bool_str_to_latex ---

def test_bool_str_to_latex_single_var():
    assert edupal.bool_str_to_latex('y = x0') == r'y(x_{0})=x_{0}'


def test_bool_str_to_latex_and():
    assert edupal.bool_str_to_latex('y = x0 & x1') == r'y(x_{1}, x_{0})=x_{1}x_{0}'


def test_bool_str_to_latex_complement():
    assert edupal.bool_str_to_latex('y = ~x0') == r'y(x_{0})=\olsi{x_{0}}'


def test_bool_str_to_latex_minimize():
    # x0 & x1 | x0 & ~x1  ==  x0; after Espresso x1 disappears from inputs too
    assert edupal.bool_str_to_latex('y = x0 & x1 | x0 & ~x1', minimize=True) == r'y(x_{0})=x_{0}'


# --- 3-level logic ---

def test_expr_to_latex_expr_pos():
    # Product of sums (POS): AND of two OR terms — 3 levels deep (AND > OR > var).
    # Both ORs have all-literal children so they are sorted and parenthesised.
    # The AND children are non-literals, so \land is used.
    # The two OR factors may appear in either order (frozenset), so we accept both.
    x0, x1, x2, x3 = exprvar('x0'), exprvar('x1'), exprvar('x2'), exprvar('x3')
    result = edupal.expr_to_latex_expr((x0 | x1) & (x2 | x3))
    assert result in {
        r'(x_{1} \lor x_{0}) \land (x_{3} \lor x_{2})',
        r'(x_{3} \lor x_{2}) \land (x_{1} \lor x_{0})',
    }


def test_expr_to_latex_expr_sop_with_nested_or():
    # SOP where one product term itself contains an OR factor (3 levels: OR > AND > OR > var).
    # x0&x1 renders as a pure-literal AND → 'x_{1}x_{0}' (no \land).
    # x2&(x3|x4) is a mixed AND → \land; the inner OR is all-literal → sorted and parenthesised.
    # The two product terms may appear in either order in the top-level OR.
    x0, x1, x2, x3, x4 = [exprvar(f'x{i}') for i in range(5)]
    result = edupal.expr_to_latex_expr((x0 & x1) | (x2 & (x3 | x4)))
    assert r'\lor' in result                        # top-level OR
    assert 'x_{1}x_{0}' in result                  # pure-literal AND term
    assert r'(x_{4} \lor x_{3})' in result         # inner OR: sorted, parenthesised
    assert r'\land' in result                       # mixed AND uses \land
    assert 'x_{2}' in result                        # literal in nested AND
