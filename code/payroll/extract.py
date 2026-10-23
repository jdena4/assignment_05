"""
extract.py — the **E** in ETL.  *(This module is provided for you.)*

Extract gets the data *out* of the files and into pandas, and does nothing else.
Every value is read as **text** (`dtype=str`): a DataFrame that has already
guessed the types for you has already hidden something from you.

Two sources:

- **The employee roster** — one row per *person*, exported from HR's new system.
  HR's system writes names as `"Moss, Pete"`.
- **Weekly payroll exports** — one file per Friday, one row per *person paid that
  week*: `payrolldate, employeeid, hours, rate, total`. That is the file the
  Assignment 04 app downloads for the payroll provider.

  But the Assignment 04 app only went live on **2026-09-25**. Before that, the
  office manager typed the same five columns into a spreadsheet by hand, and it
  shows: dates like `"8/14/2026"`, IDs like `" e004"` or `"E4"`, money like
  `"$1,029.00"`. A quarter of history is half one format and half the other.

`load_export` adds one column of its own, `source_file`, so every row remembers
which file it came from. That is lineage across files: when a number looks wrong
in a report, `source_file` tells you which week to open.

You do not modify this file, but you *do* need to read it — and run it. You cannot
clean data you have not looked at.
"""

import glob
import os
import random
from datetime import date, timedelta

import pandas as pd

# data/ sits beside code/ at the repository root, whatever folder the app or the
# tests were started from.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
EMPLOYEES_FILE = os.path.join(DATA_DIR, "employees.csv")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")


def load_employees() -> pd.DataFrame:
    """The roster: one row per employee.

    Columns: `employee_id` (always `"E001"`-style), `name` (`"Moss, Pete"`),
    `department`, `hourly_rate` (text, `"$18.00"`).
    """
    return pd.read_csv(EMPLOYEES_FILE, dtype=str)


def load_export(source) -> pd.DataFrame:
    """One weekly payroll export, plus a `source_file` column naming the file.

    `source` is a path (`"data/exports/payroll_2026-09-25.csv"`) or an uploaded
    file from `st.file_uploader` — `pd.read_csv` accepts either, and both have a
    name to record.

    Columns: `payrolldate`, `employeeid`, `hours`, `rate`, `total` — all text,
    exactly as the file has them — and `source_file`.
    """
    export = pd.read_csv(source, dtype=str)
    name = getattr(source, "name", source)
    export["source_file"] = os.path.basename(str(name))
    return export


def export_files() -> list[str]:
    """Paths of every export in data/exports/, oldest week first."""
    return sorted(glob.glob(os.path.join(EXPORTS_DIR, "payroll_*.csv")))


def load_all_exports() -> list[pd.DataFrame]:
    """Every export in data/exports/, loaded, as a list of DataFrames (one per week)."""
    return [load_export(path) for path in export_files()]


# --- Generated history: the reason you cannot hardcode -------------------------------

ROSTER_RATES = {
    "E001": 18.50, "E002": 17.75, "E003": 19.00, "E004": 20.25,
    "E005": 16.50, "E006": 18.00, "E007": 21.00, "E008": 16.50,
    "E009": 18.50, "E010": 19.50, "E011": 17.00, "E012": 17.50,
}


def gross_pay(hours: float, rate: float) -> float:
    """Assignment 04's pay rule: time-and-a-half for every hour over 40, to the cent."""
    regular = min(hours, 40.0)
    overtime = max(hours - 40.0, 0.0)
    return round(regular * rate + overtime * rate * 1.5, 2)


def _old_style_id(rng: random.Random, employee_id: str) -> str:
    """The ways an ID got typed into the old spreadsheet."""
    number = int(employee_id[1:])
    return rng.choice([
        employee_id,                 # E004
        f"e{number:03d}",            # e004
        f" {employee_id}",           # " E004"
        f"E{number}",                # E4
        f"e{number} ",               # "e4 "
    ])


def _old_style_date(rng: random.Random, day: date) -> str:
    """US-style dates, sometimes zero-padded, sometimes not."""
    if rng.random() < 0.5:
        return day.strftime("%m/%d/%Y")
    return f"{day.month}/{day.day}/{day.year}"


def _money(amount: float) -> str:
    """Dollars the way the old spreadsheet showed them: "$1,029.00"."""
    return f"${amount:,.2f}"


def _week_rows(rng: random.Random, day: date, old_style: bool) -> list[dict]:
    """One Friday's export rows: 8 to 12 employees, old- or new-style text."""
    worked = sorted(rng.sample(sorted(ROSTER_RATES), rng.randint(8, 12)))
    rows = []
    for employee_id in worked:
        hours = rng.randint(6, 46) + rng.choice([0.0, 0.25, 0.5, 0.75])
        rate = ROSTER_RATES[employee_id]
        total = gross_pay(hours, rate)
        if old_style:
            rows.append({
                "payrolldate": _old_style_date(rng, day),
                "employeeid": _old_style_id(rng, employee_id),
                "hours": rng.choice([f"{hours:.2f}", f" {hours}", f"{hours}"]),
                "rate": _money(rate),
                "total": _money(total),
            })
        else:
            rows.append({
                "payrolldate": day.isoformat(),
                "employeeid": employee_id,
                "hours": str(hours),
                "rate": str(rate),
                "total": str(total),
            })
    return rows


def generate_history(seed: int) -> list[pd.DataFrame]:
    """A made-up run of weekly exports, the same every time for the same seed.

    Between 4 and 7 consecutive Fridays. The early weeks are old-spreadsheet style
    (US dates, messy IDs, `$` money) and the later weeks are Assignment 04 style
    (ISO dates, clean IDs, plain numbers) — the same split as the real quarter.
    Each week pays 8 to 12 of the 12 employees, so some people miss some weeks.

    Returns a list of DataFrames, one per week, shaped exactly like `load_export`'s
    (including `source_file`). The tests run your pipeline on several seeds.
    """
    rng = random.Random(seed)
    weeks = rng.randint(4, 7)
    switch = rng.randint(1, weeks - 1)  # weeks before this are old-style
    first = date(2026, 7, 3) + timedelta(weeks=rng.randint(0, 10))
    exports = []
    for i in range(weeks):
        day = first + timedelta(weeks=i)
        frame = pd.DataFrame(_week_rows(rng, day, old_style=i < switch), dtype=str)
        frame["source_file"] = f"payroll_{day.isoformat()}.csv"
        exports.append(frame)
    return exports


if __name__ == "__main__":
    print(load_employees())
    exports = load_all_exports()
    print(f"{len(exports)} exports in data/exports/")
    print(exports[0].head())      # an old-spreadsheet week
    print(exports[-1].head())     # an Assignment 04 week
    print(generate_history(42)[0])
