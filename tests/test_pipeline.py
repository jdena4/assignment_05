"""Pipeline & app tests — each step on small hand-built frames, then the real quarter, then the page.

Three kinds of check:

- **Lineage** (row-level steps): same rows in and out, every input column still
  there and unchanged, exactly the expected new columns, caller's frame untouched.
- **Grain** (group-by and reshape steps): the right columns in the right order,
  one row per employee / month, the right numbers — and the history they were
  handed left alone.
- **The page**, driven with Streamlit's AppTest: upload exports, change filters,
  read the metrics.

Every DataFrame test is **scoped**: a summarize test is handed a history that is
already clean, so it passes when `summarize_employees` works, even if Step 1 is
still broken. If a scoped test passes and a `build_history` / real-quarter test
fails, the function is fine and something upstream is feeding it bad data.
"""

import datetime
import glob

import pandas as pd
import pytest

from helpers import (
    assert_lineage,
    assert_unmodified,
    export_upload,
    load_app,
    metrics,
    no_exception,
    page_text,
    repo_path,
    snapshot,
    upload_exports,
    widget,
)
from payroll import (
    add_clean_columns,
    add_date_parts,
    add_roster,
    build_history,
    combine_exports,
    generate_history,
    hours_grid,
    load_all_exports,
    load_employees,
    missed_weeks,
    pay_by_month,
    summarize_employees,
)

APP = "code/payroll_report_app.py"
RAW_COLUMNS = ["payrolldate", "employeeid", "hours", "rate", "total", "source_file"]
CLEAN_COLUMNS = ["employee_id", "pay_date", "hours_worked", "rate_usd", "gross_pay"]
SUMMARY_COLUMNS = [
    "employee_id", "display_name", "department",
    "weeks_paid", "total_hours", "total_pay", "avg_hours", "overtime_weeks",
]

# --- Hand-built inputs -----------------------------------------------------------------
# One old-spreadsheet week and one Assignment 04 week, small enough to check by hand.

WEEK_OLD = pd.DataFrame({
    "payrolldate": ["8/7/2026", "08/07/2026", "8/7/2026"],
    "employeeid": [" e001", "E3", "e12 "],
    "hours": [" 31.5", "42.00", "10"],
    "rate": ["$18.50", "$19.00", "$17.50"],
    "total": ["$582.75", "$817.00", "$175.00"],
    "source_file": ["payroll_2026-08-07.csv"] * 3,
}, dtype=str)

WEEK_NEW = pd.DataFrame({
    "payrolldate": ["2026-08-14"] * 3,
    "employeeid": ["E001", "E002", "E099"],      # E099 is not on the roster
    "hours": ["40.0", "45.5", "8.0"],
    "rate": ["18.5", "17.75", "20.0"],
    "total": ["740.0", "856.44", "160.0"],
    "source_file": ["payroll_2026-08-14.csv"] * 3,
}, dtype=str)

ROSTER = pd.DataFrame({
    "employee_id": ["E001", "E002", "E003", "E005", "E012"],     # E005 is never paid
    "name": ["Job, Anita", "Tefarian, Ross", "Erchief, Hank", "O'Furniture, Patty", "Moni, Otto"],
    "department": ["Barista", "Barista", "Kitchen", "Register", "Barista"],
    "hourly_rate": ["$18.50", "$17.75", "$19.00", "$16.50", "$17.50"],
}, dtype=str)


def combined():
    return pd.concat([WEEK_OLD, WEEK_NEW], ignore_index=True)


def cleaned():
    """The combined weeks with Step 1's clean columns, built by hand (not by your code)."""
    frame = combined()
    frame["employee_id"] = ["E001", "E003", "E012", "E001", "E002", "E099"]
    frame["pay_date"] = pd.to_datetime(["2026-08-07"] * 3 + ["2026-08-14"] * 3)
    frame["hours_worked"] = [31.5, 42.0, 10.0, 40.0, 45.5, 8.0]
    frame["rate_usd"] = [18.5, 19.0, 17.5, 18.5, 17.75, 20.0]
    frame["gross_pay"] = [582.75, 817.0, 175.0, 740.0, 856.44, 160.0]
    return frame


def history():
    """A finished history (all of Steps 1 and 2's row-level columns), built by hand."""
    frame = cleaned()
    frame["week_ending"] = ["2026-08-07"] * 3 + ["2026-08-14"] * 3
    frame["month"] = ["2026-08"] * 6
    frame["display_name"] = ["Anita Job", "Hank Erchief", "Otto Moni", "Anita Job", "Ross Tefarian", float("nan")]
    frame["department"] = ["Barista", "Kitchen", "Barista", "Barista", "Barista", float("nan")]
    return frame


# --- Step 1: history.py --------------------------------------------------------------


def test_combine_exports_stacks_every_row():
    old, new = snapshot(WEEK_OLD), snapshot(WEEK_NEW)
    out = combine_exports([WEEK_OLD, WEEK_NEW])

    assert isinstance(out, pd.DataFrame), "combine_exports should return a DataFrame"
    assert len(out) == 6, f"3 rows + 3 rows should stack to 6, got {len(out)}"
    assert list(out.columns) == RAW_COLUMNS, f"columns should stay {RAW_COLUMNS}, got {list(out.columns)}"
    assert list(out["source_file"]) == ["payroll_2026-08-07.csv"] * 3 + ["payroll_2026-08-14.csv"] * 3, (
        "rows should stay in order: every row of the first export, then the second"
    )
    assert list(out.index) == list(range(6)), (
        f"index should be 0..5, got {list(out.index)} — use ignore_index=True so each week's "
        "row numbers don't repeat"
    )
    assert_unmodified(WEEK_OLD, old, "combine_exports")
    assert_unmodified(WEEK_NEW, new, "combine_exports")


def test_add_clean_columns_keeps_lineage():
    before = combined()
    handed = combined()
    out = add_clean_columns(handed)
    assert_lineage(before, out, CLEAN_COLUMNS, "add_clean_columns")
    assert_unmodified(handed, before, "add_clean_columns")


def test_add_clean_columns_values():
    out = add_clean_columns(combined())
    assert list(out["employee_id"]) == ["E001", "E003", "E012", "E001", "E002", "E099"], (
        f"employee_id should be the roster form of every ID, got {list(out['employee_id'])}"
    )
    assert pd.api.types.is_datetime64_any_dtype(out["pay_date"]), "pay_date should be datetimes"
    assert list(out["pay_date"].dt.strftime("%Y-%m-%d")) == ["2026-08-07"] * 3 + ["2026-08-14"] * 3, (
        "pay_date should read both the US and the ISO dates"
    )
    assert list(out["hours_worked"]) == [31.5, 42.0, 10.0, 40.0, 45.5, 8.0]
    assert list(out["rate_usd"]) == [18.5, 19.0, 17.5, 18.5, 17.75, 20.0]
    assert list(out["gross_pay"]) == [582.75, 817.0, 175.0, 740.0, 856.44, 160.0]


def test_add_date_parts_keeps_lineage():
    before = cleaned()
    handed = cleaned()
    out = add_date_parts(handed)
    assert_lineage(before, out, ["week_ending", "month"], "add_date_parts")
    assert_unmodified(handed, before, "add_date_parts")


def test_add_date_parts_values():
    out = add_date_parts(cleaned())
    assert list(out["week_ending"]) == ["2026-08-07"] * 3 + ["2026-08-14"] * 3, (
        f"week_ending should be the pay date as 'YYYY-MM-DD' text, got {list(out['week_ending'])}"
    )
    assert list(out["month"]) == ["2026-08"] * 6, (
        f"month should be the pay date as 'YYYY-MM' text, got {list(out['month'])}"
    )


# --- Step 2: summarize.py -------------------------------------------------------------


def dated():
    frame = cleaned()
    frame["week_ending"] = ["2026-08-07"] * 3 + ["2026-08-14"] * 3
    frame["month"] = ["2026-08"] * 6
    return frame


def test_add_roster_keeps_lineage():
    before = dated()
    handed = dated()
    roster = snapshot(ROSTER)
    out = add_roster(handed, ROSTER)
    assert_lineage(before, out, ["display_name", "department"], "add_roster")
    assert_unmodified(handed, before, "add_roster")
    assert_unmodified(ROSTER, roster, "add_roster (the roster)")


def test_add_roster_matches_and_keeps_the_unmatched():
    out = add_roster(dated(), ROSTER)
    assert list(out["display_name"].iloc[:5]) == [
        "Anita Job", "Hank Erchief", "Otto Moni", "Anita Job", "Ross Tefarian",
    ], "display_name should be 'First Last' from the roster's 'Last, First', row by row"
    assert list(out["department"].iloc[:5]) == ["Barista", "Kitchen", "Barista", "Barista", "Barista"]
    assert pd.isna(out["department"].iloc[5]) and pd.isna(out["display_name"].iloc[5]), (
        "E099 is not on the roster: its row must survive, with NaN in the roster columns "
        "(a one-sided merge — not the default inner)"
    )
    assert "E005" not in set(out["employee_id"]), (
        "E005 is on the roster but was never paid — it must not appear in the history"
    )


def test_build_history_chains_every_step():
    old, new, roster = snapshot(WEEK_OLD), snapshot(WEEK_NEW), snapshot(ROSTER)
    out = build_history([WEEK_OLD, WEEK_NEW], ROSTER)

    expected = RAW_COLUMNS + CLEAN_COLUMNS + ["week_ending", "month", "display_name", "department"]
    assert sorted(out.columns) == sorted(expected), (
        f"build_history should return every raw and added column; missing "
        f"{sorted(set(expected) - set(out.columns))}, extra {sorted(set(out.columns) - set(expected))}"
    )
    assert len(out) == 6, f"6 rows in, {len(out)} out"
    assert round(out["gross_pay"].sum(), 2) == 3331.19
    assert out["department"].isna().sum() == 1, "only E099 should be unmatched"
    assert_unmodified(WEEK_OLD, old, "build_history")
    assert_unmodified(WEEK_NEW, new, "build_history")
    assert_unmodified(ROSTER, roster, "build_history (the roster)")


def test_build_history_real_quarter():
    out = build_history(load_all_exports(), load_employees())
    assert len(out) == 113, f"the quarter has 113 rows across 12 exports, got {len(out)}"
    assert out["week_ending"].nunique() == 12, "12 weekly exports should give 12 distinct weeks"
    assert out["pay_date"].isna().sum() == 0, "every real pay date should parse — check both formats"
    assert out["department"].isna().sum() == 0, (
        "every real row should match the roster — an unmatched row means an ID was not "
        "normalized (is 'E4' becoming 'E004'?)"
    )
    assert round(out["hours_worked"].sum(), 2) == 3107.0
    assert round(out["gross_pay"].sum(), 2) == 57761.63


# seed -> (rows, weeks, total hours, total pay, missed (employee, week) pairs)
SEEDED = {
    3: (55, 5, 1586.75, 29532.29, 5),
    7: (57, 6, 1530.25, 28399.61, 15),
    9: (67, 7, 1711.5, 31589.66, 17),
    42: (41, 4, 1155.0, 21959.84, 7),
}


@pytest.mark.parametrize("seed", sorted(SEEDED))
def test_pipeline_on_generated_history(seed):
    rows, weeks, hours, pay, missed = SEEDED[seed]
    out = build_history(generate_history(seed), load_employees())
    assert len(out) == rows, f"generate_history({seed}) has {rows} rows, got {len(out)}"
    assert out["week_ending"].nunique() == weeks, f"generate_history({seed}) covers {weeks} weeks"
    assert out["department"].isna().sum() == 0, f"generate_history({seed}): some IDs did not match the roster"
    assert round(out["hours_worked"].sum(), 2) == hours
    assert round(out["gross_pay"].sum(), 2) == pay
    assert len(missed_weeks(hours_grid(out))) == missed, (
        f"generate_history({seed}) has {missed} missed (employee, week) pairs"
    )


def test_summarize_employees_shape():
    handed = history()
    before = snapshot(handed)
    out = summarize_employees(handed)

    assert list(out.columns) == SUMMARY_COLUMNS, f"columns should be {SUMMARY_COLUMNS}, got {list(out.columns)}"
    assert list(out["employee_id"]) == ["E001", "E002", "E003", "E012"], (
        "one row per rostered employee in the history, sorted by employee_id "
        "(E099 has no department, so a group-by leaves it out)"
    )
    assert list(out.index) == [0, 1, 2, 3], "use reset_index() so the grouped keys become columns"
    assert_unmodified(handed, before, "summarize_employees")


def test_summarize_employees_values():
    out = summarize_employees(history()).set_index("employee_id")
    anita = out.loc["E001"]
    assert anita["display_name"] == "Anita Job" and anita["department"] == "Barista"
    assert anita["weeks_paid"] == 2
    assert anita["total_hours"] == pytest.approx(71.5)
    assert anita["total_pay"] == pytest.approx(1322.75)
    assert anita["avg_hours"] == pytest.approx(35.75)
    assert anita["overtime_weeks"] == 0
    assert list(out["overtime_weeks"]) == [0, 1, 1, 0], (
        "overtime_weeks counts weeks with MORE than 40.0 hours — 40.0 exactly is not overtime"
    )


def test_summarize_employees_real_quarter():
    out = summarize_employees(build_history(load_all_exports(), load_employees()))
    assert len(out) == 12, f"12 employees were paid this quarter, got {len(out)} rows"
    assert round(out["total_pay"].sum(), 2) == 57761.63, "every dollar in the history belongs to someone"
    ross = out.set_index("employee_id").loc["E002"]
    assert (ross["weeks_paid"], ross["total_hours"], ross["total_pay"], ross["avg_hours"], ross["overtime_weeks"]) == (
        9, 315.0, 5684.44, 35.0, 3
    ), f"E002 should be 9 weeks, 315.0 h, $5,684.44, 35.0 avg, 3 overtime weeks; got {ross.to_dict()}"


# --- Step 3: reshape.py ---------------------------------------------------------------


def test_hours_grid_hand_built():
    handed = history()
    before = snapshot(handed)
    grid = hours_grid(handed)

    assert list(grid.columns) == ["employee_id", "display_name", "2026-08-07", "2026-08-14"], (
        f"columns should be the two name columns then one per week in date order, got {list(grid.columns)}"
    )
    assert list(grid["employee_id"]) == ["E001", "E002", "E003", "E012"]
    assert grid[["2026-08-07", "2026-08-14"]].values.tolist() == [
        [31.5, 40.0], [0.0, 45.5], [42.0, 0.0], [10.0, 0.0],
    ], "each cell is that employee's hours that week, and 0 (not NaN) when they were not paid"
    assert list(grid.index) == [0, 1, 2, 3], "use reset_index() so the grid has a plain index"
    assert_unmodified(handed, before, "hours_grid")


def test_hours_grid_real_quarter():
    grid = hours_grid(build_history(load_all_exports(), load_employees()))
    weeks = list(grid.columns[2:])
    assert len(grid) == 12 and len(weeks) == 12, f"expected 12 employees x 12 weeks, got {grid.shape}"
    assert weeks == sorted(weeks) and weeks[0] == "2026-08-07" and weeks[-1] == "2026-10-23"
    assert not grid[weeks].isna().any().any(), "no NaN in the grid — fill_value=0"
    assert round(grid[weeks].sum().sum(), 2) == 3107.0, "the grid holds every hour in the history"


def test_missed_weeks_hand_built():
    grid = pd.DataFrame({
        "employee_id": ["E001", "E002", "E003", "E012"],
        "display_name": ["Anita Job", "Ross Tefarian", "Hank Erchief", "Otto Moni"],
        "2026-08-07": [31.5, 0.0, 42.0, 10.0],
        "2026-08-14": [40.0, 45.5, 0.0, 0.0],
    })
    before = snapshot(grid)
    out = missed_weeks(grid)

    assert list(out.columns) == ["employee_id", "display_name", "week_ending", "hours_worked"], (
        f"columns should be employee_id, display_name, week_ending, hours_worked — got {list(out.columns)}"
    )
    assert out[["employee_id", "week_ending"]].values.tolist() == [
        ["E002", "2026-08-07"], ["E003", "2026-08-14"], ["E012", "2026-08-14"],
    ], "only the zero cells, sorted by employee_id then week_ending"
    assert (out["hours_worked"] == 0).all()
    assert list(out.index) == [0, 1, 2], "reset the index after filtering"
    assert_unmodified(grid, before, "missed_weeks")


def test_missed_weeks_real_quarter():
    out = missed_weeks(hours_grid(build_history(load_all_exports(), load_employees())))
    assert len(out) == 31, f"the quarter has 31 missed (employee, week) pairs, got {len(out)}"
    pete = list(out[out["employee_id"] == "E006"]["week_ending"])
    assert pete == ["2026-08-21", "2026-09-11", "2026-09-18", "2026-10-02", "2026-10-23"], (
        f"Pete Moss (E006) missed 5 weeks, got {pete}"
    )


def test_pay_by_month_hand_built():
    handed = history()
    before = snapshot(handed)
    out = pay_by_month(handed)

    assert list(out.columns) == ["month", "Barista", "Kitchen"], (
        f"columns should be month then one per department, got {list(out.columns)}"
    )
    assert out.values.tolist() == [["2026-08", 2354.19, 817.0]], (
        "Barista is 582.75 + 175.00 + 740.00 + 856.44 = 2354.19, Kitchen 817.00"
    )
    assert_unmodified(handed, before, "pay_by_month")


def test_pay_by_month_real_quarter():
    out = pay_by_month(build_history(load_all_exports(), load_employees()))
    assert list(out.columns) == ["month", "Barista", "Kitchen", "Register"]
    assert list(out["month"]) == ["2026-08", "2026-09", "2026-10"]
    assert out.set_index("month").loc["2026-09"].tolist() == [5561.28, 7172.27, 3624.01]
    assert round(out[["Barista", "Kitchen", "Register"]].sum().sum(), 2) == 57761.63


# --- The app ----------------------------------------------------------------------------


def all_exports():
    return [export_upload(path) for path in sorted(glob.glob(repo_path("data", "exports", "*.csv")))]


def test_app_starts_quiet():
    app = load_app(APP)
    no_exception(app, APP)
    text = page_text(app)
    assert "Salt City Coffee — Quarterly Payroll Report" in text, "the page needs its title"
    uploader = widget(app.file_uploader, "exports", "file_uploader")
    assert uploader is not None
    assert not app.metric, "nothing below the uploader should appear before a file is chosen"


def test_app_reports_the_whole_quarter():
    app = load_app(APP)
    upload_exports(app, all_exports())
    app.run()
    no_exception(app, APP)

    shown = metrics(app)
    assert shown.get("Weeks") == "12", f"Weeks should be 12, page shows {shown.get('Weeks')}"
    assert shown.get("Employees") == "12"
    assert shown.get("Total hours") == "3,107.00", f"Total hours should be '3,107.00', got {shown.get('Total hours')}"
    assert shown.get("Total gross pay") == "$57,761.63"
    assert len(app.dataframe) >= 3, "the page should show the employee summary, the hours grid and the missed weeks"
    assert len(app.get("download_button")) == 1, "the accountant's CSV needs an st.download_button"
    assert app.get("vega_lite_chart") or app.get("arrow_vega_lite_chart"), "pay by month should be an st.bar_chart"
    assert not app.warning, "the real quarter has no unmatched IDs — no warning expected"


def test_app_filters_by_department_and_dates():
    app = load_app(APP)
    upload_exports(app, all_exports())
    app.run()

    widget(app.selectbox, "department", "selectbox").set_value("Kitchen")
    app.run()
    shown = metrics(app)
    assert shown.get("Employees") == "4", "Kitchen has 4 employees"
    assert shown.get("Total gross pay") == "$23,393.45"

    widget(app.date_input, "dates", "date_input").set_value((datetime.date(2026, 9, 1), datetime.date(2026, 9, 30)))
    app.run()
    no_exception(app, APP)
    shown = metrics(app)
    assert shown.get("Weeks") == "4", "September has 4 pay dates"
    assert shown.get("Total hours") == "354.50"
    assert shown.get("Total gross pay") == "$7,172.27", (
        "Kitchen in September should match the September/Kitchen cell of pay_by_month"
    )


def test_app_warns_about_unmatched_ids():
    bad_week = (
        "payrolldate,employeeid,hours,rate,total\n"
        "2026-10-30,E001,30.0,18.5,555.0\n"
        "2026-10-30,E77,12.0,18.0,216.0\n"
    )
    app = load_app(APP)
    upload_exports(app, [("payroll_2026-10-30.csv", bad_week.encode(), "text/csv")])
    app.run()
    no_exception(app, APP)
    assert app.warning, "an ID that is not on the roster should raise an st.warning"
    assert "E77" in app.warning[0].value, "the warning should name the unmatched ID"
    assert metrics(app).get("Total gross pay") == "$555.00", "the unmatched row is left out of the totals"
