from pyeda.inter import expr as pyeda_expr, exprvar

from edupal.function_finder import find_2level_term_count, term_count_cnf, term_count_dnf


def test_no_filter_returns_all_functions():
    # 2 inputs → 2^(2^2) = 16 boolean functions
    results = find_2level_term_count(['x0', 'x1'])
    assert len(results) == 16


def test_filter_dnf_only():
    results = find_2level_term_count(['x0', 'x1'], mdf_pred=lambda d: d == 1)
    assert all(m.dnf_terms == 1 for m in results)
    assert len(results) > 0


def test_filter_cnf_only():
    results = find_2level_term_count(['x0', 'x1'], mcf_pred=lambda c: c == 1)
    assert all(m.cnf_terms == 1 for m in results)
    assert len(results) > 0


def test_filter_both():
    results = find_2level_term_count(
        ['x0', 'x1', 'x2'],
        mdf_pred=lambda d: d > 3,
        mcf_pred=lambda c: c < 4,
    )
    assert all(m.dnf_terms > 3 and m.cnf_terms < 4 for m in results)
    assert len(results) == 8


def test_result_fields():
    results = find_2level_term_count(['x0', 'x1'])
    for m in results:
        assert hasattr(m, 'tt_int')
        assert hasattr(m, 'dnf_terms')
        assert hasattr(m, 'cnf_terms')
        assert hasattr(m, 'expr_dnf_min')
        assert hasattr(m, 'expr_cnf')


# --- term_count_dnf ---

def test_term_count_dnf_variable():
    assert term_count_dnf(exprvar('x0')) == 1


def test_term_count_dnf_complement():
    assert term_count_dnf(~exprvar('x0')) == 1


def test_term_count_dnf_and():
    # A single product term (AND) counts as 1
    x0, x1 = exprvar('x0'), exprvar('x1')
    assert term_count_dnf(x0 & x1) == 1


def test_term_count_dnf_or_two_terms():
    # OR of two AND terms: 2 product terms
    x0, x1, x2, x3 = exprvar('x0'), exprvar('x1'), exprvar('x2'), exprvar('x3')
    assert term_count_dnf((x0 & x1) | (x2 & x3)) == 2


def test_term_count_dnf_constant_one():
    # Constant 1 treated as a single (tautology) term
    assert term_count_dnf(pyeda_expr('1')) == 1


def test_term_count_dnf_constant_zero():
    # Constant 0: no terms (unsatisfiable)
    assert term_count_dnf(pyeda_expr('0')) == 0


# --- term_count_cnf ---

def test_term_count_cnf_variable():
    assert term_count_cnf(exprvar('x0')) == 1


def test_term_count_cnf_complement():
    assert term_count_cnf(~exprvar('x0')) == 1


def test_term_count_cnf_or():
    # A single OR clause counts as 1
    x0, x1 = exprvar('x0'), exprvar('x1')
    assert term_count_cnf(x0 | x1) == 1


def test_term_count_cnf_and_two_clauses():
    # AND of two OR clauses: 2 clauses
    x0, x1, x2, x3 = exprvar('x0'), exprvar('x1'), exprvar('x2'), exprvar('x3')
    assert term_count_cnf((x0 | x1) & (x2 | x3)) == 2


def test_term_count_cnf_constant_one():
    # Constant 1 is an empty conjunction: 0 clauses
    assert term_count_cnf(pyeda_expr('1')) == 0


def test_term_count_cnf_constant_zero():
    # Constant 0 is an unsatisfiable single clause
    assert term_count_cnf(pyeda_expr('0')) == 1
