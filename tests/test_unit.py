"""Unit tests — the four Series functions, one value at a time.

Each function takes a whole column and returns a whole column, but the column
can be one value long. So every test below builds a one-row Series, runs the
function, and checks the one value that comes back — then a last test per
function checks that a longer Series comes back the same length, in the same
order, with the same index.

When one of these fails, the test name and the input tell you exactly which
spelling your function does not handle yet.
"""

import pandas as pd
import pytest

from payroll import clean_employee_id, clean_number, format_name, parse_pay_date


def one(function, value):
    """Run a Series function on a one-value Series; return the one value back."""
    result = function(pd.Series([value]))
    assert isinstance(result, pd.Series), (
        f"{function.__name__} should return a Series (a whole column), got {type(result).__name__}"
    )
    assert len(result) == 1, f"{function.__name__} turned 1 value into {len(result)}"
    return result.iloc[0]


def assert_same_shape(function, values):
    series = pd.Series(values, index=[10 + i for i in range(len(values))])
    result = function(series)
    assert isinstance(result, pd.Series), f"{function.__name__} should return a Series"
    assert list(result.index) == list(series.index), (
        f"{function.__name__} changed the index — return one value per input value, in the same order"
    )


# --- clean_employee_id -------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("E004", "E004"),      # already clean
        ("e004", "E004"),      # lower case
        (" E004", "E004"),     # leading space
        ("E012 ", "E012"),     # trailing space
        ("E4", "E004"),        # not zero-padded
        ("e10 ", "E010"),      # all three at once
        ("E7", "E007"),
    ],
)
def test_clean_employee_id(raw, expected):
    assert one(clean_employee_id, raw) == expected, f"clean_employee_id({raw!r}) should be {expected!r}"


def test_clean_employee_id_keeps_shape():
    assert_same_shape(clean_employee_id, ["e1", " E002", "E3 "])


# --- clean_number ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("$18.50", 18.5),
        ("17.75", 17.75),
        ("$1,029.00", 1029.0),     # thousands separator
        (" 35.25", 35.25),         # stray space
        ("41.75", 41.75),
        ("N/A", 0.0),              # unreadable -> zero
        ("", 0.0),
        (None, 0.0),               # missing -> zero
    ],
)
def test_clean_number(raw, expected):
    got = one(clean_number, raw)
    assert isinstance(got, float), f"clean_number({raw!r}) should be a float, got {type(got).__name__}"
    assert got == pytest.approx(expected), f"clean_number({raw!r}) should be {expected}"


def test_clean_number_keeps_shape():
    assert_same_shape(clean_number, ["$1.00", "2", "bad"])


# --- parse_pay_date -------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("08/14/2026", "2026-08-14"),    # old spreadsheet, zero-padded
        ("8/14/2026", "2026-08-14"),     # old spreadsheet, not padded
        ("9/4/2026", "2026-09-04"),
        ("2026-09-25", "2026-09-25"),    # Assignment 04 export
        ("2026-10-02", "2026-10-02"),
    ],
)
def test_parse_pay_date(raw, expected):
    got = one(parse_pay_date, raw)
    assert not pd.isna(got), f"parse_pay_date({raw!r}) came back NaT — it should read as {expected}"
    assert pd.Timestamp(got) == pd.Timestamp(expected), f"parse_pay_date({raw!r}) should be {expected}, got {got}"


@pytest.mark.parametrize("raw", ["someday", "", "13/45/2026"])
def test_parse_pay_date_unreadable_is_nat(raw):
    got = one(parse_pay_date, raw)
    assert pd.isna(got), f"parse_pay_date({raw!r}) should be NaT (unreadable), got {got}"


def test_parse_pay_date_returns_datetimes():
    result = parse_pay_date(pd.Series(["8/7/2026", "2026-09-25", "junk"], index=[5, 6, 7]))
    assert pd.api.types.is_datetime64_any_dtype(result), (
        f"parse_pay_date should return a datetime Series (dtype datetime64), got {result.dtype}. "
        "Use pd.to_datetime, not string slicing."
    )
    assert list(result.index) == [5, 6, 7], "parse_pay_date changed the index"


# --- format_name ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Moss, Pete", "Pete Moss"),
        ("O'Furniture, Patty", "Patty O'Furniture"),
        ("Docktur-Indahaus,Sara", "Sara Docktur-Indahaus"),   # no space after the comma
        ("  Job ,  Anita ", "Anita Job"),                      # stray spaces
    ],
)
def test_format_name(raw, expected):
    assert one(format_name, raw) == expected, f"format_name({raw!r}) should be {expected!r}"


def test_format_name_keeps_shape():
    assert_same_shape(format_name, ["Moss, Pete", "Job, Anita"])

