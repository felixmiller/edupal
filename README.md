# eduPAL

**eduPAL** provides reusable helper utilities for lecture notes in **digital circuits**.

The package targets teaching-oriented **PAL-style (Programmable Array Logic)** workflows,
with utilities for generating figures and typeset expressions that embed directly into
LaTeX-driven course materials.

## Features

- Convert truth tables to **WaveDrom** JSON (`l/h/x` states, dot-extension for holds)
- Wrap-around context (pre/post) to visualize periodic sequences
- Optional randomization of the displayed sequence (including context duplicates)
- Generate **LaTeX truth tables** (`tabular` / `tabularx`) from truth table data
- Render **boolean expressions** in LaTeX math notation (DNF, CNF, CDNF, CCNF)
- **Minimize** boolean expressions via Espresso (pyeda)
- **Enumerate and filter** all boolean functions over a set of inputs by DNF/CNF term count

## Install

```bash
pip install edupal
```

Or from source:

```bash
git clone https://github.com/felixmiller/eduPAL
cd eduPAL
pip install -e .
```

## Modules

### `wavedrom_utils` — Truth table → WaveDrom

Convert a combinational truth table to a WaveDrom JSON object for timing diagram rendering.

```python
from edupal import truth_table_to_wavedrom, set_linewidth

wd = truth_table_to_wavedrom(
    inputs=['x0', 'x1', 'x2'],
    output_name='y',
    truth='00101100',       # or an integer: 0b00101100
    pre_context=1,
    post_context=1,
    randomize=False,
)
wd = set_linewidth(wd, lw=2)
```

- `truth` accepts a bit string (`'0'`/`'1'`/`'x'`) or a non-negative integer
- `pre_context`/`post_context`: wrap-around rows prepended/appended for context
- `randomize` + `seed`: shuffle the displayed sequence reproducibly

### `latex_utils` — Boolean algebra → LaTeX

Generate LaTeX code for truth tables and boolean expressions.

```python
from edupal import (
    truth_table_to_latex,
    truth_table_to_latex_custom,
    cdnf_to_latex,
    ccnf_to_latex,
    tt_str_min_to_latex_str,
    bool_str_to_latex,
)

# Truth table as tabular environment
print(truth_table_to_latex([0, 0, 1, 1, 0, 1, 1, 0]))

# CDNF / CCNF compact notation: \Sigma(...) / \Pi(...)
print(cdnf_to_latex('00101100'))   # \Sigma(2, 4, 5)
print(ccnf_to_latex('00101100'))   # \Pi(0, 1, 3, 6, 7)

# Minimized expression via Espresso
print(tt_str_min_to_latex_str('00101100', ['x2','x1','x0'], 'y'))

# From a boolean expression string
print(bool_str_to_latex('y = x0 & ~x1 | x2', minimize=True))
```

### `function_finder` — Enumerate boolean functions

Search all boolean functions over a given set of inputs, optionally filtering by
the number of minimized DNF terms or CNF clauses.

```python
from edupal.function_finder import find_2level_term_count

# Find all 3-input functions with more than 3 DNF terms but fewer than 4 CNF clauses
matches = find_2level_term_count(
    inputs=['x0', 'x1', 'x2'],
    mdf_pred=lambda d: d > 3,
    mcf_pred=lambda c: c < 4,
)
for m in matches:
    print(m.tt_int, m.dnf_terms, m.cnf_terms)
```

Each result is a `FunctionMatch` with fields `tt_int`, `dnf_terms`, `cnf_terms`,
`expr_dnf_min`, and `expr_cnf`.

## Dependencies

- [pyeda](https://pyeda.readthedocs.io) — boolean algebra and Espresso minimization
- [schemdraw](https://schemdraw.readthedocs.io) — circuit diagram rendering
- [matplotlib](https://matplotlib.org)

## License

MIT
