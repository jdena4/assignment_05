"""
explore.py — run the pipeline one step at a time.  *(Provided for you.)*

Tests do not stop at breakpoints; this script does. Open it, set a breakpoint on
any line below (or inside one of your functions), and run it with
Run and Debug -> "Python Debugger: Current File". Each step prints the shape of
what came back and its first few rows, so you can see a column appear the moment
your function adds it.

A step you have not written yet returns None, and the script says so and stops
there — so it is useful from the first function to the last.
"""

import pandas as pd

from payroll import (
    add_clean_columns,
    add_date_parts,
    add_roster,
    combine_exports,
    hours_grid,
    load_all_exports,
    load_employees,
    missed_weeks,
    pay_by_month,
    summarize_employees,
)

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)


def show(label: str, frame) -> None:
    """Print one step's result, or stop with a hint if the step is not written yet."""
    print(f"\n=== {label}")
    if frame is None:
        print("    returned None — this function is still a stub. Write it, run again.")
        raise SystemExit(0)
    print(f"    {frame.shape[0]} rows x {frame.shape[1]} columns")
    print(frame.head(6))


exports = load_all_exports()
employees = load_employees()
print(f"{len(exports)} weekly exports, {len(employees)} employees on the roster")

history = combine_exports(exports)
show("Step 1: combine_exports", history)

history = add_clean_columns(history)
show("Step 1: add_clean_columns", history)

history = add_date_parts(history)
show("Step 1: add_date_parts", history)

history = add_roster(history, employees)
show("Step 2: add_roster", history)

show("Step 2: summarize_employees", summarize_employees(history))

grid = hours_grid(history)
show("Step 3: hours_grid", grid)
show("Step 3: missed_weeks", missed_weeks(grid))
show("Step 3: pay_by_month", pay_by_month(history))
