"""
Find combinational boolean function with specific properties.

Features:
- Enumerate all truth tables for a given set of input variables.
- For each function:
    - Minimize F using Espresso to get a compact DNF-like expression (SOP).
    - Convert that minimized expression to CNF (via to_cnf()).
- Count DNF/CNF terms.
- Apply optional predicates on these counts.
- Return detailed records per function.
"""

from typing import Callable, Iterable, List, NamedTuple, Optional

import pyeda
from pyeda.inter import espresso_tts, truthtable, ttvar


# --- Helpers to count terms in expressions ---
def term_count_dnf(f: pyeda.boolalg.expr.Expression) -> int:
    """
    Count DNF 'terms' on a minimized SOP-like expression:
      - Or of product terms: number of terms = len(f.xs)
      - Single product (AND): 1
      - Single literal (Variable/Complement): 1
      - Constant 1: 1 (treat as a single term)
      - Constant 0: 0 (no terms)
    """
    if isinstance(f, pyeda.boolalg.expr.OrOp):
        return len(f.xs)
    elif isinstance(f, pyeda.boolalg.expr.AndOp):
        return 1
    elif isinstance(f, pyeda.boolalg.expr.Variable):
        return 1
    elif isinstance(f, pyeda.boolalg.expr.Complement):
        return 1
    elif isinstance(f, pyeda.boolalg.expr._One):
        return 1
    elif isinstance(f, pyeda.boolalg.expr._Zero):
        return 0
    else:
        raise TypeError(f'DNF count: unsupported expression type {type(f)}')


def term_count_cnf(f: pyeda.boolalg.expr.Expression) -> int:
    """
    Count CNF 'clauses' on a CNF expression:
      - And of clauses: number of clauses = len(f.xs)
      - Single clause (OR of literals): 1
      - Single literal (Variable/Complement): 1
      - Constant 1: 0 (true has an empty conjunction)
      - Constant 0: 1 (false is typically an unsatisfiable single empty clause)
    """
    if isinstance(f, pyeda.boolalg.expr.AndOp):
        return len(f.xs)
    elif isinstance(f, pyeda.boolalg.expr.OrOp):
        return 1
    elif isinstance(f, pyeda.boolalg.expr.Variable):
        return 1
    elif isinstance(f, pyeda.boolalg.expr.Complement):
        return 1
    elif isinstance(f, pyeda.boolalg.expr._One):
        return 0
    elif isinstance(f, pyeda.boolalg.expr._Zero):
        return 1
    else:
        raise TypeError(f'CNF count: unsupported expression type {type(f)}')


# --- Structured result type for clarity ---
class FunctionMatch(NamedTuple):
    tt_int: int
    dnf_terms: int
    cnf_terms: int
    expr_dnf_min: pyeda.boolalg.expr.Expression  # minimized SOP-like expression of F
    expr_cnf: pyeda.boolalg.expr.Expression      # CNF(F) derived via to_cnf()


# --- Main search ---
def find_2level_term_count(
    inputs: Iterable[str],
    mdf_pred: Optional[Callable[[int], bool]] = None,  # None = no filter on DNF term count
    mcf_pred: Optional[Callable[[int], bool]] = None,  # None = no filter on CNF clause count
) -> List[FunctionMatch]:
    """
    Enumerate all Boolean functions over `inputs` (n variables => 2^(2^n) functions).

    For each function:
      - Construct the truth table for F.
      - Minimize F via Espresso -> expr_dnf_min (SOP-like).
      - Build CNF(F) via expr_dnf_min.to_cnf() -> expr_cnf.
      - Count terms/clauses and apply optional predicates.

    Returns: List[FunctionMatch]
    """
    inputs = list(inputs)
    n = len(inputs)
    tt_vars = [ttvar(x) for x in inputs]

    bitlen = 1 << n              # 2**n (rows in TT)
    num_functions = 1 << bitlen  # 2**(2**n) (number of Boolean functions)

    results: List[FunctionMatch] = []
    for tt_int in range(num_functions):
        # Bitstring MSB-first, reversed for PyEDA's expectations:
        bits = format(tt_int, f'0{bitlen}b')

        tt_F = truthtable(tt_vars, reversed(bits))

        # Espresso returns a list of minimized expressions; take the first
        simp_F_list = espresso_tts(tt_F)
        if not simp_F_list:
            continue

        expr_dnf_min = simp_F_list[0]              # minimized SOP-like expression for F
        expr_cnf = expr_dnf_min.to_cnf()           # CNF(F) (NOTE: not minimized; canonical CNF)

        dnf_terms = term_count_dnf(expr_dnf_min)
        cnf_terms = term_count_cnf(expr_cnf)

        # Apply optional predicates
        passes = True
        if mdf_pred is not None:
            passes = passes and bool(mdf_pred(dnf_terms))
        if mcf_pred is not None:
            passes = passes and bool(mcf_pred(cnf_terms))

        if passes:
            results.append(FunctionMatch(
                tt_int=tt_int,
                dnf_terms=dnf_terms,
                cnf_terms=cnf_terms,
                expr_dnf_min=expr_dnf_min,
                expr_cnf=expr_cnf,
            ))

    return results


if __name__ == "__main__":
    # --- Examples ---
    inputs = ['x0', 'x1', 'x2']

    # 4) Both filters
    fs4 = find_2level_term_count(
        inputs,
        mdf_pred=lambda d: d > 3,
        mcf_pred=lambda c: c < 4,
    )
    print(f"Filter: {len(fs4)}")  # expect 8
    for f in fs4:
        print(f)

