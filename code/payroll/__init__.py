"""
payroll — the pipeline behind the quarterly report app.  *(Provided for you.)*

    from payroll import load_employees, load_export, build_history, summarize_employees

Three steps in three modules, after the provided extract:

    extract.py     load the roster and the weekly exports              (given)
    history.py     Step 1 — combine, then .str and dates into columns  (you)
    summarize.py   Step 2 — roster on, then group by employee          (you)
    reshape.py     Step 3 — pivot_table and melt                       (you)

Same as Assignment 04: every name below must exist in its module, even before
you have written its body, or `import payroll` fails and every test goes red at
once. That is why the stubs keep every function signature.
"""

from .extract import (
    export_files,
    generate_history,
    load_all_exports,
    load_employees,
    load_export,
)
from .history import (
    add_clean_columns,
    add_date_parts,
    clean_employee_id,
    clean_number,
    combine_exports,
    parse_pay_date,
)
from .reshape import hours_grid, missed_weeks, pay_by_month
from .summarize import add_roster, build_history, format_name, summarize_employees

__all__ = [
    "load_employees",
    "load_export",
    "export_files",
    "load_all_exports",
    "generate_history",
    "clean_employee_id",
    "clean_number",
    "parse_pay_date",
    "combine_exports",
    "add_clean_columns",
    "add_date_parts",
    "format_name",
    "add_roster",
    "build_history",
    "summarize_employees",
    "hours_grid",
    "missed_weeks",
    "pay_by_month",
]
