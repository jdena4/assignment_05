"""Code structure tests — read the source and check the pipeline is built the right way.

The pipeline tests check what your functions *return*. These check *how*: that
Step 1 cleans with vectorized `.str` and `pd.to_datetime` rather than looping,
that Step 2 summarizes with a group-by and named aggregation, that Step 3
reshapes with `pivot_table` and `melt`, that the row-level steps still follow
the lineage rule, and that the app assembles the pipeline instead of redoing it.

Everything here reads the **parsed** source (`ast`), not the text, so a technique
mentioned in a comment does not count. When a test fails, the message names the
file and the exact thing it was looking for.
"""

import ast

from helpers import repo_path

HISTORY = "code/payroll/history.py"
SUMMARIZE = "code/payroll/summarize.py"
RESHAPE = "code/payroll/reshape.py"
APP = "code/payroll_report_app.py"
PIPELINE_MODULES = (HISTORY, SUMMARIZE, RESHAPE)

# The columns the source files give you. A pipeline step may READ these; it may
# never assign to them.
INPUT_COLUMNS = {
    "payrolldate", "employeeid", "hours", "rate", "total", "source_file",
    "name", "department", "hourly_rate",
}

# Ways to destroy lineage. None of them belong in this pipeline — named
# aggregation means nothing ever needs renaming.
LINEAGE_BREAKERS = {"drop", "rename", "pop", "insert", "drop_duplicates"}

# Row-at-a-time tools. This week the column methods (.str, .dt, to_numeric,
# to_datetime) do the looping for you.
ROW_LOOPS = {"apply", "map", "applymap", "iterrows", "itertuples"}


# --- Reading the source ---------------------------------------------------------------


def parse(script: str) -> ast.Module:
    with open(repo_path(script), encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=script)


def calls(tree: ast.AST) -> list[ast.Call]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)]


def call_name(node: ast.Call) -> str:
    """`pd.merge(...)` -> "merge"; `s.str.strip()` -> "strip"; `float(x)` -> "float"."""
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def called_names(tree: ast.AST) -> set[str]:
    return {call_name(node) for node in calls(tree)}


def calls_named(tree: ast.AST, name: str) -> list[ast.Call]:
    return [node for node in calls(tree) if call_name(node) == name]


def keyword_value(node: ast.Call, name: str):
    for keyword in node.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return keyword.value.value
    return None


def has_keyword(node: ast.Call, name: str) -> bool:
    return any(keyword.arg == name for keyword in node.keywords)


def attributes(tree: ast.AST) -> list[str]:
    return [node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)]


def function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name}() not found")


def imported_modules(tree: ast.Module) -> set[str]:
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def assigned_columns(tree: ast.AST) -> list[str]:
    """Every column name assigned with `frame["name"] = ...` or `frame.name = ...`."""
    names = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant):
                names.append(str(target.slice.value))
            elif isinstance(target, ast.Attribute):
                names.append(target.attr)
    return names


def lineage_violations(script: str) -> list[str]:
    tree = parse(script)
    problems = []
    for name in sorted(set(assigned_columns(tree)) & INPUT_COLUMNS):
        problems.append(f"assigns to input column {name!r} — clean into a NEW column instead")
    for node in calls(tree):
        name = call_name(node)
        if name in LINEAGE_BREAKERS:
            problems.append(f"calls .{name}() — a pipeline step never removes or renames a column")
        if keyword_value(node, "inplace") is True:
            problems.append("uses inplace=True — pipeline steps return a new frame, they do not mutate")
    for node in ast.walk(tree):
        if isinstance(node, ast.Delete):
            problems.append("uses `del` — columns are never removed")
    return problems


# --- Step 1 -----------------------------------------------------------------------------


def test_history_cleans_with_str_methods_not_loops():
    """Step 1 uses .str methods on whole columns — no apply, map, or row loops."""
    tree = parse(HISTORY)
    used = attributes(tree)
    called = called_names(tree)

    assert used.count("str") >= 4, (
        f"{HISTORY} should clean text with the .str accessor (series.str.strip(), .str.upper(), "
        f".str.zfill(), .str.replace()) — found .str {used.count('str')} time(s)"
    )
    for method in ("strip", "upper", "zfill", "replace"):
        assert method in called, f"{HISTORY} should use .str.{method}()"
    loops = sorted(called & ROW_LOOPS)
    assert not loops, (
        f"{HISTORY} uses {loops}. This step is vectorized: .str and pd.to_numeric work on a whole "
        "column at once, so no function needs to be applied one value at a time."
    )
    numeric = calls_named(tree, "to_numeric")
    assert numeric and all(keyword_value(n, "errors") == "coerce" for n in numeric), (
        f"{HISTORY}: clean_number should use pd.to_numeric(..., errors='coerce') so unreadable "
        "values become NaN instead of crashing"
    )


def test_history_parses_dates_with_explicit_formats():
    """Every pd.to_datetime names its format and coerces; add_date_parts uses .dt."""
    tree = parse(HISTORY)
    parses = calls_named(tree, "to_datetime")

    assert len(parses) >= 2, (
        f"{HISTORY}: parse_pay_date needs pd.to_datetime twice — once per date format — found {len(parses)}"
    )
    for node in parses:
        assert has_keyword(node, "format"), (
            f"{HISTORY} line {node.lineno}: pd.to_datetime without format= guesses, and guesses "
            "differ between computers. Name the format ('%m/%d/%Y' or '%Y-%m-%d')."
        )
        assert keyword_value(node, "errors") == "coerce", (
            f"{HISTORY} line {node.lineno}: pd.to_datetime needs errors='coerce' so the other "
            "format becomes NaT instead of an exception"
        )
    date_parts = function(tree, "add_date_parts")
    assert "dt" in attributes(date_parts) and "strftime" in called_names(date_parts), (
        f"{HISTORY}: add_date_parts should format pay_date with .dt.strftime(...)"
    )


def test_history_combines_with_concat():
    """combine_exports stacks with pd.concat and a fresh index."""
    concats = calls_named(parse(HISTORY), "concat")
    assert concats, f"{HISTORY}: combine_exports should stack the weeks with pd.concat(...)"
    assert any(keyword_value(node, "ignore_index") is True for node in concats), (
        f"{HISTORY}: pd.concat needs ignore_index=True — otherwise every week brings its own row 0"
    )


# --- Step 2 -----------------------------------------------------------------------------


def test_summarize_groups_with_named_aggregation():
    """summarize_employees is a groupby + named .agg + reset_index; add_roster is a one-sided merge."""
    tree = parse(SUMMARIZE)
    summarize = function(tree, "summarize_employees")
    called = called_names(summarize)

    assert "groupby" in called, f"{SUMMARIZE}: summarize_employees should use .groupby(...)"
    aggs = calls_named(summarize, "agg") + calls_named(summarize, "aggregate")
    assert aggs, f"{SUMMARIZE}: summarize_employees should compute its columns with .agg(...)"
    assert any(len(node.keywords) >= 5 for node in aggs), (
        f"{SUMMARIZE}: use named aggregation — .agg(weeks_paid=('week_ending', 'count'), ...) — "
        "one keyword per output column, so nothing needs renaming afterwards"
    )
    assert "reset_index" in called, (
        f"{SUMMARIZE}: the grouped keys end up in the index; .reset_index() brings them back as columns"
    )

    merges = calls_named(function(tree, "add_roster"), "merge")
    assert merges, f"{SUMMARIZE}: add_roster should combine the frames with pd.merge(...)"
    hows = [keyword_value(node, "how") for node in merges]
    assert "left" in hows or "right" in hows, (
        f"{SUMMARIZE}: add_roster merges with how={hows} (None means the default, inner) — every "
        "history row must survive, so it is how='left' (or how='right' with the frames swapped)"
    )

    names = function(tree, "format_name")
    assert "split" in called_names(names) and "str" in attributes(names), (
        f"{SUMMARIZE}: format_name should split names with .str.split(',')"
    )
    assert not called_names(names) & ROW_LOOPS, f"{SUMMARIZE}: format_name should use .str, not apply/map"


def test_build_history_reuses_every_step():
    """build_history chains the functions you wrote rather than re-implementing them."""
    called = called_names(function(parse(SUMMARIZE), "build_history"))
    for step in ("combine_exports", "add_clean_columns", "add_date_parts", "add_roster"):
        assert step in called, f"{SUMMARIZE}: build_history should call {step}()"


# --- Step 3 -----------------------------------------------------------------------------


def test_reshape_uses_pivot_table_and_melt():
    """The grid and the monthly table are pivot_tables with fill_value; missed_weeks melts."""
    tree = parse(RESHAPE)
    for name in ("hours_grid", "pay_by_month"):
        pivots = calls_named(function(tree, name), "pivot_table")
        assert pivots, f"{RESHAPE}: {name} should reshape with .pivot_table(...)"
        assert any(has_keyword(node, "fill_value") for node in pivots), (
            f"{RESHAPE}: {name} needs fill_value= so an empty cell is a 0, not NaN"
        )
    assert "melt" in called_names(function(tree, "missed_weeks")), (
        f"{RESHAPE}: missed_weeks should turn the grid back into rows with .melt(...)"
    )


# --- Lineage and loops, across the whole pipeline -----------------------------------------


def test_pipeline_keeps_lineage_and_never_loops_over_rows():
    """No input column is overwritten, nothing is dropped or renamed, no iterrows anywhere."""
    problems = []
    for script in PIPELINE_MODULES:
        problems.extend(f"{script}: {p}" for p in lineage_violations(script))
        for name in sorted(called_names(parse(script)) & {"iterrows", "itertuples"}):
            problems.append(f"{script}: calls .{name}() — let pandas do the looping")
    assert not problems, "\n".join(problems)

    assigned = assigned_columns(parse(HISTORY))
    for expected in ("employee_id", "pay_date", "hours_worked", "rate_usd", "gross_pay", "week_ending", "month"):
        assert expected in assigned, f"{HISTORY}: no step assigns the {expected!r} column"


# --- The app --------------------------------------------------------------------------------


def test_app_assembles_the_pipeline():
    """The page loads, builds, summarizes and reshapes through the pipeline, with the required widgets."""
    tree = parse(APP)
    called = called_names(tree)

    assert "payroll" in imported_modules(tree), f"{APP} should import from the payroll package"
    for name in ("load_employees", "load_export", "build_history", "summarize_employees",
                 "hours_grid", "missed_weeks", "pay_by_month"):
        assert name in called, f"{APP} should call {name}() — the app assembles the pipeline, it does not re-do it"
    for widget in ("file_uploader", "selectbox", "date_input", "metric", "bar_chart",
                   "dataframe", "download_button", "warning"):
        assert widget in called, f"{APP} should use st.{widget}(...)"
    uploads = calls_named(tree, "file_uploader")
    assert any(keyword_value(node, "accept_multiple_files") is True for node in uploads), (
        f"{APP}: the uploader takes a whole quarter of files — accept_multiple_files=True"
    )
    assert "dt" in attributes(tree), f"{APP}: filter the pay dates through the .dt accessor"
    reshaping = sorted(called & {"groupby", "pivot_table", "pivot", "melt"})
    assert not reshaping, f"{APP} calls {reshaping} — reshaping belongs in the pipeline, the page only shows it"
    assert "print" not in called and "input" not in called, f"{APP}: use widgets, not the console"
