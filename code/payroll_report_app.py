"""
payroll_report_app.py — the quarter at a glance, for someone who never opens a terminal.

Every Friday since September the office manager at Salt City Coffee has downloaded
a payroll export from the Assignment 04 app; before that she typed the same file
by hand. The owner now wants to know where the hours went this quarter, the
accountant wants pay by month and department, and the manager wants to see who
has been missing shifts. This page answers all three from the pile of exports.

Same shape as Assignment 04: the page *assembles* the pipeline — one call to
`build_history` does the cleaning — and then shows the reports, filtered by the
department and dates the user picks.

Run it:  Run and Debug -> "Streamlit Run: Current File"
Test it: pytest tests/test_pipeline.py -k app
"""
# --- The page ---------------------------------------------------------------------
#
# No scaffolding. Every function this page needs already exists in the payroll
# package, and every widget it needs you used in Assignments 03 and 04 — plus two
# new ones, st.date_input and st.bar_chart. README Step 8 has the exact widgets,
# keys and labels; the tests in tests/test_pipeline.py -k app check them.
#
# The shape, in words:
#
#   title and a sentence of instructions
#   roster   <- load_employees()                           (fixed; not uploaded)
#   uploads  <- st.file_uploader, key="exports", accept_multiple_files=True
#               (an empty list until files are chosen)
#   if there are uploads:
#       history <- build_history([load_export(u) for u in uploads], roster)
#       st.warning naming any employeeid with no department (not on the roster);
#           the reports below use only the rows that matched
#       st.selectbox, key="department": "All" plus each department
#       st.date_input, key="dates": a (start, end) range, defaulting to the first
#           and last pay_date — compare against pay_date.dt.date to filter
#       the selection as a subheader
#       four st.metric cards in st.columns(4): Weeks, Employees, Total hours,
#           Total gross pay — counts are .nunique(), totals are .sum()
#       st.bar_chart of pay_by_month(selected), with month as the x axis
#       st.dataframe of summarize_employees(selected)
#       st.dataframe of hours_grid(selected), then of missed_weeks(that grid)
#       st.download_button, key="download": pay_by_month(...).to_csv(index=False)
#
# What the page does NOT do: cleaning, grouping, pivoting. If you find yourself
# writing a groupby or a pivot_table here, that logic belongs in the package.

import streamlit as st

from payroll import (
    build_history,
    hours_grid,
    load_employees,
    load_export,
    missed_weeks,
    pay_by_month,
    summarize_employees,
)

st.title("Salt City Coffee — Quarterly Payroll Report")
st.write(
    "Upload the weekly payroll exports for the quarter, then pick a department "
    "and a date range to see hours, pay, overtime and missed shifts."
)

roster = load_employees()
uploads = st.file_uploader(
    "Weekly payroll exports (CSV)",
    type=["csv"],
    accept_multiple_files=True,
    key="exports",
)

if uploads:
    history = build_history([load_export(u) for u in uploads], roster)

    unmatched = history[history["department"].isna()]
    if not unmatched.empty:
        ids = ", ".join(sorted(unmatched["employeeid"].unique()))
        st.warning(
            f"These employee IDs are not on the roster and are left out of the "
            f"report: {ids}"
        )
    matched = history[history["department"].notna()]

    departments = ["All"] + sorted(matched["department"].unique())
    department = st.selectbox("Department", departments, key="department")

    first = history["pay_date"].min().date()
    last = history["pay_date"].max().date()
    dates = st.date_input(
        "Pay dates",
        value=(first, last),
        min_value=first,
        max_value=last,
        key="dates",
    )
    start, end = dates if len(dates) == 2 else (dates[0], dates[0])

    pay_days = matched["pay_date"].dt.date
    in_range = (pay_days >= start) & (pay_days <= end)
    if department == "All":
        selected = matched[in_range]
    else:
        selected = matched[in_range & (matched["department"] == department)]

    st.subheader(f"{department} · {start:%b %d, %Y} to {end:%b %d, %Y}")
    if selected.empty:
        st.info("No pay dates match this department and date range.")
        st.stop()

    weeks_col, people_col, hours_col, pay_col = st.columns(4)
    weeks_col.metric("Weeks", selected["week_ending"].nunique())
    people_col.metric("Employees", selected["employee_id"].nunique())
    hours_col.metric("Total hours", f"{selected['hours_worked'].sum():,.2f}")
    pay_col.metric("Total gross pay", f"${selected['gross_pay'].sum():,.2f}")

    monthly = pay_by_month(selected)
    st.subheader("Gross pay by month and department")
    st.bar_chart(monthly, x="month")

    st.subheader("Employee summary")
    st.dataframe(summarize_employees(selected), hide_index=True)

    grid = hours_grid(selected)
    st.subheader("Hours by week")
    st.dataframe(grid, hide_index=True)

    st.subheader("Missed weeks")
    st.dataframe(missed_weeks(grid), hide_index=True)

    st.download_button(
        "Download pay by month (CSV)",
        data=monthly.to_csv(index=False),
        file_name="pay_by_month.csv",
        mime="text/csv",
        key="download",
    )
