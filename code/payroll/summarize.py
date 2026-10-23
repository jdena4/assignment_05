"""
summarize.py — Step 2 of the pipeline: the roster on, then one row per employee.

Two halves:

1. **Finish the history** — put a readable name and a department on every row
   (one more `.str` function and a merge you have written before), and chain
   Steps 1 and 2 into `build_history`, the one call the app makes.
2. **Change the grain** — `summarize_employees` turns *one row per person per
   week* into *one row per person*. That is a **group by**: split the rows into
   groups that share a key, compute something for each group, combine the answers
   into a new table (lesson 3-5).

A group-by does not break the lineage rule; it starts a *new* table at a new
grain, and every number in it is traceable to a group of rows in the history.
What it must not do is change the history it was handed.

Less scaffolding here: the steps are described, the code is yours.
"""

import pandas as pd

from .history import add_clean_columns, add_date_parts, combine_exports


def format_name(names: pd.Series) -> pd.Series:
    """Turn HR's `"Last, First"` into `"First Last"`, for a whole Series.

        "Moss, Pete"              ->  "Pete Moss"
        "O'Furniture, Patty"      ->  "Patty O'Furniture"
        "Docktur-Indahaus,Sara"   ->  "Sara Docktur-Indahaus"   # no space after ","
        "  Job ,  Anita "         ->  "Anita Job"               # stray spaces

    Steps: split every value on the comma with `.str.split(",")` — each value
    becomes a list, and `.str[0]` / `.str[1]` pick an item out of every list.
    Strip each part, then join them back together in the other order with a
    space between. Same `.str` toolkit as `clean_employee_id`; no `apply`.
    """
    # TODO: your code here
    pass


def add_roster(history: pd.DataFrame, employees: pd.DataFrame) -> pd.DataFrame:
    """Return the history with two roster columns added: display_name, department.

    One row per history row, in the same order — every week anyone was paid
    stays, and an `employee_id` that is not on the roster gets `NaN` in both new
    columns rather than vanishing. Rostered people who were never paid do not
    appear. That is the same one-sided merge as Assignment 04's Step 2
    (`how="left"` with the history on the left, or `how="right"` with the frames
    swapped).

    Steps: work on a copy of the roster, add `display_name` to it with
    `format_name`, keep only the three columns the history needs
    (`employee_id`, `display_name`, `department`), and merge that onto the
    history on `employee_id`. The history must have been through
    `add_clean_columns` first — the raw `employeeid` does not match anything.
    """
    # TODO: your code here
    pass


def build_history(exports: list, employees: pd.DataFrame) -> pd.DataFrame:
    """Raw exports and roster in; the finished quarter history out.

    Chain the steps you have written, in order: `combine_exports`,
    `add_clean_columns`, `add_date_parts`, `add_roster`. Call them; do not re-do
    their work. The result has every raw column, every column the steps add, and
    one row per row of every export.
    """
    # TODO: your code here
    pass


def summarize_employees(history: pd.DataFrame) -> pd.DataFrame:
    """One row per employee: how many weeks, how many hours, how much pay.

    Group the history by `employee_id`, `display_name` and `department` (all
    three, so all three come out as columns) and compute, for each group:

    | column           | from            | how                                  |
    | ---------------- | --------------- | ------------------------------------ |
    | `weeks_paid`     | `week_ending`   | count                                |
    | `total_hours`    | `hours_worked`  | sum                                  |
    | `total_pay`      | `gross_pay`     | sum, rounded to cents                |
    | `avg_hours`      | `hours_worked`  | mean, rounded to 2 places            |
    | `overtime_weeks` | `hours_worked`  | how many of the weeks are over 40.0  |

    Return exactly those eight columns, in the order `employee_id, display_name,
    department, weeks_paid, total_hours, total_pay, avg_hours, overtime_weeks`,
    one row per employee sorted by `employee_id`, with a plain 0, 1, 2, ... index
    (the grouped columns end up in the index until you `reset_index()` —
    lesson 3-5).

    Use **named aggregation** — `.agg(new_name=("column", "how"))` — so the
    columns come out with the right names and nothing needs renaming. `"how"`
    can be a function, too: a lambda that receives one group's hours as a Series.

    Rows with no `department` (an ID that was not on the roster) are left out
    of a group-by by default. The app warns about them; this function does not
    need to.
    """
    # TODO: your code here
    pass
