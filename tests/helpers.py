"""Shared helpers for the tests.

The one that matters is `assert_lineage`: it is how every pipeline test checks
that a step *added* to a DataFrame without changing anything it was given.
"""

import os

import pandas as pd
from streamlit.testing.v1 import AppTest

# tests/ lives directly under the repository root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo_path(*parts: str) -> str:
    """Build an absolute path from the repository root, whatever the working directory."""
    return os.path.join(REPO_ROOT, *parts)


def assert_lineage(before: pd.DataFrame, after: pd.DataFrame, added: list[str], step: str) -> None:
    """The lineage rule, as four assertions.

    A pipeline step must return a frame that:

    1. has the same number of rows as it was given,
    2. still has every input column, with every value unchanged (order does not matter),
    3. adds exactly the columns listed in `added` — no more, no fewer,
    4. did not modify the frame it was given (the caller still holds the original).

    `before` is a *snapshot* of the input taken before the step ran, which is what
    makes rule 4 checkable: compare it to the object the step was actually handed.
    """
    assert isinstance(after, pd.DataFrame), f"{step} should return a DataFrame, got {type(after).__name__}"
    assert len(after) == len(before), (
        f"{step} changed the row count: {len(before)} rows in, {len(after)} out. "
        "A pipeline step adds columns, never rows — and never loses them."
    )
    missing = [c for c in before.columns if c not in after.columns]
    assert not missing, f"{step} dropped input column(s) {missing} — lineage is lost"

    kept = after[list(before.columns)].reset_index(drop=True)
    original = before.reset_index(drop=True)
    changed = [c for c in before.columns if not kept[c].astype(str).equals(original[c].astype(str))]
    assert not changed, (
        f"{step} changed the values in input column(s) {changed}. Clean into a NEW "
        "column; the raw value stays where it was."
    )
    new = [c for c in after.columns if c not in before.columns]
    assert sorted(new) == sorted(added), (
        f"{step} should add exactly {sorted(added)}; it added {sorted(new)}"
    )


def snapshot(frame: pd.DataFrame) -> pd.DataFrame:
    """A deep copy to compare against after a step has run."""
    return frame.copy(deep=True)


def assert_unmodified(handed: pd.DataFrame, before: pd.DataFrame, step: str) -> None:
    """The frame the step was handed still looks exactly like it did before the call."""
    assert list(handed.columns) == list(before.columns) and handed.astype(str).equals(before.astype(str)), (
        f"{step} modified the DataFrame it was given. Start with `.copy()` and add "
        "columns to the copy — the caller's frame is not yours to change."
    )


# --- Streamlit ----------------------------------------------------------------------

TEXT_ELEMENTS = (
    "title", "header", "subheader", "markdown", "text", "caption",
    "info", "success", "warning", "error",
)


def load_app(script: str) -> AppTest:
    """Load a Streamlit script from the repository and run it once, as opening it would."""
    app = AppTest.from_file(repo_path(script), default_timeout=60)
    app.run()
    return app


def page_text(app: AppTest) -> str:
    """Everything readable on the page, joined into one string."""
    parts = []
    for element_type in TEXT_ELEMENTS:
        parts.extend(str(element.value) for element in app.get(element_type))
    for metric in app.metric:
        parts.append(f"{metric.label}: {metric.value}")
    return "\n".join(parts)


def metrics(app: AppTest) -> dict[str, str]:
    """The page's st.metric cards as {label: value}; values are the displayed strings."""
    return {metric.label: str(metric.value) for metric in app.metric}


def widget(elements, key: str, kind: str):
    """The widget with `key=`, or the only widget of that kind, or a clear error."""
    for element in elements:
        if getattr(element, "key", None) == key:
            return element
    if len(elements) == 1:
        return elements[0]
    raise AssertionError(f"expected one st.{kind} (or one with key={key!r}), found {len(elements)}")


def export_path(week: str) -> str:
    """data/exports/payroll_<week>.csv"""
    return repo_path("data", "exports", f"payroll_{week}.csv")


def export_upload(path: str) -> tuple[str, bytes, str]:
    """A file on disk as an st.file_uploader value: (name, bytes, mime)."""
    with open(path, "rb") as fh:
        return (os.path.basename(path), fh.read(), "text/csv")


def upload_exports(app: AppTest, files: list[tuple[str, bytes, str]]) -> None:
    """Choose several CSVs in the app's uploader at once, as if dragged into the browser."""
    uploader = widget(app.file_uploader, "exports", "file_uploader")
    uploader.set_value(files)


def no_exception(app: AppTest, script: str) -> None:
    assert not app.exception, f"{script} raised: {app.exception[0].value}"
