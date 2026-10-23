"""
reshape.py — Step 3 of the pipeline: the same numbers, turned sideways.

A **long** table has one row per observation (person, week, hours). A **wide**
table spreads one of those columns across the top, so a whole row reads like a
line on a timecard. People read wide tables; pipelines store long ones; and
lesson 3-5's `pivot_table` and `melt` turn one into the other.

Three functions:

- `hours_grid` — long to wide: employees down the side, weeks across the top.
- `missed_weeks` — wide back to long, to find something the long table could
  never show you: the weeks a person was **not** paid. Nobody's absence is a row
  in an export. It only exists once the grid has filled the gap with a zero.
- `pay_by_month` — months down the side, departments across the top: the table
  the accountant asked for, and the shape `st.bar_chart` wants.

No walkthrough. The docstrings say what each function returns; `tests/` says
how that is checked. None of these functions may change the frame it is given.
"""

import pandas as pd


def hours_grid(history: pd.DataFrame) -> pd.DataFrame:
    """Employees down the side, weeks across the top, hours in the cells.

    Columns: `employee_id`, `display_name`, then one column per `week_ending`
    (`"2026-08-07"`, `"2026-08-14"`, ...) in date order. One row per employee
    in the history, sorted by `employee_id`; a plain 0, 1, 2, ... index.

    Each cell is that employee's `hours_worked` for that week, and **0** — not
    `NaN` — for a week they were not paid. Use `pivot_table` with
    `fill_value=0`.
    """
    # TODO: your code here
    pass


def missed_weeks(grid: pd.DataFrame) -> pd.DataFrame:
    """Every (employee, week) with zero hours in the grid — the weeks people missed.

    Takes the output of `hours_grid`. Returns a long table with columns
    `employee_id`, `display_name`, `week_ending`, `hours_worked`, holding only
    the rows where `hours_worked` is 0, sorted by `employee_id` then
    `week_ending`, with a plain 0, 1, 2, ... index.

    `melt` the grid back to long (the two name columns stay put; the week
    columns become `week_ending` / `hours_worked` pairs), then keep the zeros.
    """
    # TODO: your code here
    pass


def pay_by_month(history: pd.DataFrame) -> pd.DataFrame:
    """Total gross pay by month (rows) and department (columns), to the cent.

    Columns: `month`, then one column per department in alphabetical order
    (`Barista`, `Kitchen`, `Register` for the real data). One row per `month`
    in date order; a plain 0, 1, 2, ... index. A department with nobody paid
    that month shows 0.0.

    This is the CSV the accountant imports, and — with `month` as the x axis —
    exactly the shape `st.bar_chart` draws as one bar per department.
    """
    # TODO: your code here
    pass
