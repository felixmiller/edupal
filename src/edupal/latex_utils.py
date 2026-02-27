"""
Utilities for generating LaTeX output from boolean algebra objects.

Covers:
- Truth table LaTeX formatting (:func:`truth_table_to_latex`, :func:`truth_table_to_latex_custom`)
- Expression rendering (:func:`expr_to_latex_expr`, :func:`bool_str_to_latex`)
- CDNF/CCNF notation (:func:`cdnf_to_latex`, :func:`ccnf_to_latex`,
  :func:`expr_to_cdnf_latex`, :func:`expr_to_ccnf_latex`)
- Espresso minimization helpers (:func:`tt_str_min_to_latex_str`, :func:`tt_min_to_latex_str`)
- Variable-order-aware expression wrapper (:func:`expand_and_sort`)
"""

from pyeda.boolalg.expr import OrOp, AndOp, Complement, Variable, _Zero, _One, expr
from pyeda.boolalg.minimization import espresso_exprs, espresso_tts
from pyeda.boolalg.table import ttvar, truthtable

from .strings import TRUTH_TABLE_TITLE

def truth_table_to_latex(values: list[int], input_labels: list[str] = None, output_labels: list[str] = None) -> str:
    """
    Generate LaTeX code for a truth table.

    Args:
        values (list[int]): Truth table as a list of integers.
            Each index represents an input combination.
            Each integer encodes outputs in binary.
        input_labels (list[str], optional): Labels for input columns (e.g., ['X0', 'X1']).
            If None, labels are auto-generated.
        output_labels (list[str], optional): Labels for output columns (e.g., ['Y0', 'Y1']).
            If None, labels are auto-generated.

    Returns:
        str: LaTeX code for a tabular environment representing the truth table.
    """
    if not values:
        return "% Empty truth table"

    num_rows = len(values)
    num_inputs = (num_rows).bit_length() - 1
    num_outputs = max(1, max(values).bit_length())

    # Auto-generate labels if not provided
    if input_labels is None:
        input_labels = [f"$X_{i}$" for i in range(num_inputs)]
    if output_labels is None:
        output_labels = [f"$Y_{i}$" for i in range(num_outputs)]

    # LaTeX header
    header = " & ".join(["Dec"] + input_labels + output_labels) + " \\\\ \\hline\n"

    # Rows
    rows = []
    for idx, val in enumerate(values):
        inputs = f"{idx:0{num_inputs}b}"
        outputs = f"{val:0{num_outputs}b}"
        row = " & ".join([str(idx)] + list(inputs) + list(outputs)) + " \\\\"
        rows.append(row)

    # Combine into LaTeX table
    latex_code = "\\begin{tabular}{|" + "c|" * (1 + num_inputs + num_outputs) + "}\n\\hline\n"
    latex_code += header
    latex_code += "\n".join(rows)
    latex_code += "\n\\hline\n\\end{tabular}"

    return latex_code

def truth_table_to_latex_custom(values: list[int],
                                input_labels: list[str] = None,
                                output_labels: list[str] = None,
                                table_width: str = "0.36\\textwidth",
                                title: str = None) -> str:
    r"""
    Generate LaTeX code for a truth table wrapped in a ``samepage`` environment.

    Format details:
    - No decimal column
    - Inputs and outputs separated by ``!{\vrule width 4\arrayrulewidth}``
    - Bold math headers
    - ``tabularx`` environment with custom column layout

    Args:
        values (list[int]): Truth table as a list of integers (same format as
            :func:`truth_table_to_latex`).
        input_labels (list[str], optional): Labels for input columns, MSB-first.
            If None, auto-generated as ``x_{n-1}, ..., x_0``.
        output_labels (list[str], optional): Labels for output columns, MSB-first.
            If None, auto-generated as ``y_{m-1}, ..., y_0``.
        table_width (str): LaTeX dimension string for the ``tabularx`` width.
            Default: ``"0.36\\textwidth"``.
        title (str, optional): Heading text emitted above the table as
            ``\textbf{<title>}``. Defaults to :data:`~edupal.strings.TRUTH_TABLE_TITLE`.

    Returns:
        str: LaTeX source for a ``samepage`` + ``tabularx`` truth table block.
    """
    if not values:
        return "% Empty truth table"

    if title is None:
        title = TRUTH_TABLE_TITLE

    num_rows = len(values)
    num_inputs = (num_rows).bit_length() - 1
    num_outputs = max(1, max(values).bit_length())

    # Auto-generate labels if not provided
    if input_labels is None:
        input_labels = [f"x_{i}" for i in range(num_inputs - 1, -1, -1)]
    else:
        input_labels.reverse()
    if output_labels is None:
        output_labels = [f"y_{i}" for i in range(num_outputs - 1, -1, -1)]
    else:
        output_labels.reverse()

    # Column specification: inputs | outputs separated by thick rule
    col_spec = "|".join(["Y"] * num_inputs) + f"!{{\\vrule width 4\\arrayrulewidth}}" + "|".join(["Y"] * num_outputs)

    # Header row
    header_cells = [f"$\\bm{{{lbl}}}$" for lbl in input_labels + output_labels]
    header_row = " & ".join(header_cells) + " \\\\"

    # Rows
    rows = []
    for idx, val in enumerate(values):
        inputs = f"{idx:0{num_inputs}b}"
        outputs = f"{val:0{num_outputs}b}"
        row_cells = [f"${bit}$" for bit in list(inputs) + list(outputs)]
        rows.append(" & ".join(row_cells) + " \\\\\\hline")

    # Combine LaTeX code
    latex_code = (
        "\\begin{samepage}\n"
        f"    \\textbf{{{title}}}\n\n"
        f"    \\begin{{tabularx}}{{{table_width}}}{{{col_spec}}}\n"
        f"       {header_row}\n"
        "      \\Xhline{4\\arrayrulewidth}\n"
        + "\n".join(rows) +
        "\n    \\end{tabularx}\n"
        "\\end{samepage}"
    )

    return latex_code


def expr_to_latex_expr(expr) -> str:
    r"""
    Convert a PyEDA boolean expression tree into a LaTeX math string.

    Rendering rules:

    - **Variable**: rendered with subscript notation, e.g. ``x0`` → ``x_{0}``.
    - **Complement (NOT)**: wrapped in ``\olsi{}``, e.g. ``~x0`` → ``\olsi{x_{0}}``.
    - **Constants**: ``0`` and ``1`` are rendered as-is.
    - **AND**: if *all* children are literals (Variables or Complements), they are
      concatenated without ``\land`` and sorted in *reverse* alphabetical order.
      The sort key strips a leading ``~`` so that ``~x1`` sorts alongside ``x1``.
      If *any* child is non-literal, children are joined with ``\land`` in pyeda's
      internal (unspecified) order — no additional sorting is applied.
    - **OR**: children joined with ``\lor``.  When all children are literals they
      are sorted in reverse alphabetical order (same key).  An OR group is wrapped
      in parentheses unless it is the outermost (top-level) expression.

    .. note::
        PyEDA builds AND/OR trees left-associatively for three or more operands,
        e.g. ``x0 & x1 & x2`` is stored internally as ``(x0 & x1) & x2``.  The
        inner ``AndOp`` is not a literal, so the outer AND uses ``\land``, giving
        ``x_{1}x_{0} \land x_{2}`` rather than ``x_{2}x_{1}x_{0}``.

    Args:
        expr: A PyEDA boolean expression (e.g. from :func:`pyeda.inter.exprvar`
            or :func:`pyeda.inter.expr`).

    Returns:
        str: LaTeX math string suitable for use inside ``$...$`` or ``\(...\)``.
    """

    def sort_key(obj):
        s = str(obj)
        # Remove a single leading '~' if present; do NOT strip internal tildes.
        return s[1:] if s.startswith('~') else s

    def format_var(var_name: str) -> str:
        if len(var_name) > 1 and var_name[1:].isdigit():
            return f"{var_name[0]}_{{{var_name[1:]}}}"
        return var_name

    def is_literal(node) -> bool:
        return isinstance(node, Variable) or isinstance(node, Complement)

    def recurse(node, top_level=False) -> str:
        # Sometimes we need to unpack from tuple
        if isinstance(node,tuple):
            if len(node) != 1:
                raise Exception('Not implemented')
            node = node[0]
        # OR
        if isinstance(node, OrOp):
            op_list = list(node.xs)
            if all(is_literal(x) for x in op_list):
                op_list.sort(key=sort_key, reverse=True)
            inner = " \\lor ".join(recurse(x) for x in op_list)
            return inner if top_level else f"({inner})"

        # AND
        if isinstance(node, AndOp):
            op_list = list(node.xs)
            if all(is_literal(x) for x in op_list):
                op_list.sort(key=sort_key, reverse=True)
            parts = [recurse(x) for x in op_list]
            if all(is_literal(x) for x in op_list):
                return "".join(parts)  # omit \land for pure literals
            else:
                return " \\land ".join(parts)

        # NOT
        if isinstance(node, Complement):
            inner = node.inputs[0]
            return f"\\olsi{{{recurse(inner)}}}"

        # Variable
        if isinstance(node, Variable):
            return format_var(str(node))

        # Zero
        if isinstance(node, _Zero):
            return format_var(str(0))

        # Zero
        if isinstance(node, _One):
            return format_var(str(1))

        raise TypeError(f"Unsupported expression type: {type(node)}")

    return recurse(expr, top_level=True)

def bool_str_to_latex(bool_str, minimize=False):
    """
    Convert a boolean expression string to a LaTeX math string.

    Args:
        bool_str (str): Expression in the form 'y = <pyeda expression>',
            e.g. 'y = x0 & ~x1 | x2'.
        minimize (bool): If True, minimize the expression via Espresso before
            rendering. Default: False.

    Returns:
        str: LaTeX math string of the form 'y(x_{2}, x_{1}, x_{0})=<expr>'.
    """
    outvar, bool_expr_str = [ x.strip() for x in bool_str.split('=') ]
    if minimize:
        f = espresso_exprs(expr(bool_expr_str))[0]
    else:
        f = expr(bool_expr_str)
    inputs = reversed(sorted([str(x) for x in f.inputs]))
    latex = latex_func_header(outvar,inputs) + '=' + expr_to_latex_expr(f)
    return latex


def cdnf_to_latex(tt_string: str) -> str:
    r"""
    Create LaTeX code for the compact canonical disjunctive normal form (CDNF)
    for a single output function based on its truth table string.

    Args:
        tt_string (str): A string of '0' and '1' representing the output column of the truth table.

    Returns:
        str: LaTeX representation in the form \Sigma(<indices>).
    """
    # Find positions where the output is '1'
    ones_positions = [str(i) for i, bit in enumerate(tt_string) if bit == '1']

    # Build LaTeX string
    return f"\\Sigma({', '.join(ones_positions)})"


def ccnf_to_latex(tt_string: str) -> str:
    r"""
    Create LaTeX code for the compact canonical conjunctive normal form (CNCF)
    for a single output function based on its truth table string.

    Args:
        tt_string (str): A string of '0' and '1' representing the output column of the truth table.

    Returns:
        str: LaTeX representation in the form \Pi(<indices>).
    """
    # Find positions where the output is '0'
    zeros_positions = [str(i) for i, bit in enumerate(tt_string) if bit == '0']

    # Build LaTeX string
    return f"\\Pi({', '.join(zeros_positions)})"

class _SortedExpression:
    """Wraps a pyeda expression to iterate its truth table in explicit LSB-first order.

    This object is returned by :func:`expand_and_sort`.  Its only public method
    is :meth:`iter_image`, which yields one ``bool`` per input combination in
    LSB-first order (i.e. the variable at index 0 of *vlist_lsb_first* is the
    least significant bit).
    """

    def __init__(self, ex, vlist_lsb_first):
        self._ex = ex
        self._vlist = vlist_lsb_first

    def iter_image(self):
        """Yield one bool per input combination in LSB-first variable order."""
        yield from _eval_lsb_first(self._ex, self._vlist)


def expand_and_sort(ex, vlist_lsb_first):
    """
    Wrap a pyeda expression for iteration in LSB-first variable order.

    Returns an object with an iter_image() method that yields one bool per
    input combination, where vlist_lsb_first[0] is the least significant bit.

    Args:
        ex: A pyeda boolean expression.
        vlist_lsb_first (list[str]): Variable names ordered LSB-first,
            e.g. ['x0', 'x1', 'x2'].

    Returns:
        Object with iter_image() yielding truth table values in LSB-first order.
    """
    return _SortedExpression(ex, vlist_lsb_first)


def _eval_lsb_first(ex, vlist_lsb_first):
    """Evaluate ex for each input combination with explicit LSB-first ordering.

    Yields one bool per row (2^n rows total). Row i corresponds to the
    input assignment where vlist_lsb_first[j] = (i >> j) & 1.
    """
    n = len(vlist_lsb_first)
    var_exprs = [expr(v) for v in vlist_lsb_first]
    for i in range(2**n):
        point = {var_exprs[j]: (i >> j) & 1 for j in range(n)}
        yield bool(ex.restrict(point))


def expr_to_cdnf_latex(ex, vlist_lsb_first, outvar='y'):
    r"""
    Convert a pyeda expression to a CDNF LaTeX string using \Sigma notation.

    Args:
        ex: A pyeda boolean expression.
        vlist_lsb_first (list[str]): Variable names ordered LSB-first.
        outvar (str): Output variable name for the function header. Default: 'y'.

    Returns:
        str: LaTeX string of the form 'y(x_{2}, x_{1}, x_{0})=\Sigma(2, 4, 5)'.
    """
    elmnts = [str(i) for i, v in enumerate(_eval_lsb_first(ex, vlist_lsb_first)) if v]
    return latex_func_header(outvar, reversed(vlist_lsb_first)) + '=\\Sigma(' + ','.join(elmnts) + ')'


def expr_to_ccnf_latex(ex, vlist_lsb_first, outvar='y'):
    r"""
    Convert a pyeda expression to a CCNF LaTeX string using \Pi notation.

    Args:
        ex: A pyeda boolean expression.
        vlist_lsb_first (list[str]): Variable names ordered LSB-first.
        outvar (str): Output variable name for the function header. Default: 'y'.

    Returns:
        str: LaTeX string of the form 'y(x_{2}, x_{1}, x_{0})=\Pi(0, 1, 3, 6, 7)'.
    """
    elmnts = [str(i) for i, v in enumerate(_eval_lsb_first(ex, vlist_lsb_first)) if not v]
    return latex_func_header(outvar, reversed(vlist_lsb_first)) + '=\\Pi(' + ','.join(elmnts) + ')'

def latex_func_header(func_name: str, inputs: list[str]) -> str:
    """
    Create a LaTeX string for a boolean function header in the form:
        y_{0}(x_{3}, x_{2}, x_{1})
    Assumes:
    - func_name like 'y0'
    - inputs like ['x3', 'x2', 'x1']
    """
    def to_subscript(name: str) -> str:
        # Split into letter and digit: e.g., 'x3' -> 'x_{3}'
        return f"{name[0]}_{{{name[1:]}}}"

    if any(char.isdigit() for char in func_name):
        func = to_subscript(func_name)
    else:
        func = func_name
    ins = [to_subscript(i) for i in inputs]
    return f"{func}({', '.join(ins)})"

def tt_str_min_to_latex_str(tt_string, inputs, outvar, cnf=False):
    """
    Create a LaTeX math string for a minimized boolean function (2-level logic).

    The function is minimized via Espresso to obtain a compact SOP expression.
    Optionally converts the result to CNF.

    Args:
        tt_string (str): A string of '0'/'1' representing the output column of
            the truth table, MSB-first (row 0 first).
        inputs (list[str]): Variable names MSB-first, e.g. ``['x2', 'x1', 'x0']``.
        outvar (str): Output variable name for the function header, e.g. ``'y'``.
        cnf (bool): If True, convert the minimized expression to CNF before
            rendering. Default: False.

    Returns:
        str: LaTeX math string of the form ``'y(x_{2}, x_{1}, x_{0})=<expr>'``.
    """
    tt_v = [ttvar(x) for x in inputs]
    pyeda_table = truthtable(tt_v, tt_string)
    min_func = espresso_tts(pyeda_table)
    if cnf:
        min_func = min_func[0].to_cnf()
    latex = latex_func_header(outvar,reversed(inputs)) + '=' + expr_to_latex_expr(min_func)
    return latex

def tt_min_to_latex_str(tt, inputs, outvar, cnf=False):
    """
    Create a LaTeX math string for a minimized boolean function given as an integer.

    Converts the integer truth table to a bit string and delegates to
    :func:`tt_str_min_to_latex_str`.

    Args:
        tt (int): Truth table encoded as an integer. Bit ``2^i`` corresponds to
            row ``i`` (LSB = row 0).
        inputs (list[str]): Variable names MSB-first, e.g. ``['x2', 'x1', 'x0']``.
        outvar (str): Output variable name for the function header, e.g. ``'y'``.
        cnf (bool): If True, convert the minimized expression to CNF before
            rendering. Default: False.

    Returns:
        str: LaTeX math string of the form ``'y(x_{2}, x_{1}, x_{0})=<expr>'``.
    """
    tt_string = reversed(format(tt, f'0{2**len(inputs)}b'))
    return tt_str_min_to_latex_str(tt_string, inputs, outvar, cnf=cnf)


def tt_str_to_latex_str_cdnf(tt_str, inputs, outvar):
    """
    Convert a truth table string directly to a CDNF LaTeX string.

    Args:
        tt_str (str): A string of '0'/'1' representing the output column,
            MSB-first (row 0 first).
        inputs (list[str]): Variable names MSB-first, e.g. ['x2', 'x1', 'x0'].
        outvar (str): Output variable name for the function header.

    Returns:
        str: LaTeX string of the form 'y(x_{2}, x_{1}, x_{0})=\\Sigma(2, 4, 5)'.
    """
    latex = latex_func_header(outvar,reversed(inputs)) + '=' + cdnf_to_latex(tt_str)
    return latex
