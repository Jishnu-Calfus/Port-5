"""
Decides which existing dashboard chart component should render a data
agent query's results, and reshapes those results into that component's
exact expected prop shape.

This is a plain function, never an LLM call. The agent already decided
WHAT to ask the database for; which chart best displays the answer is
something the actual returned columns can tell us for certain, so there is
nothing to gain from asking the model to guess a second time. Same rule as
sql_gateway.py: don't trust a guess for something code can verify.

The agent's own SQL can name/alias its result columns however it wants
("count(*) AS n" vs "count(*) AS total"), so nothing here assumes specific
column names except the handful of shapes that are genuinely distinctive
(negative/neutral/positive together, or a column literally called
"source") -- everything else falls back to looking at the actual values.
"""
from typing import Any

ChartData = dict | list[dict]

# Substrings (not exact names) that suggest a column represents a time
# period -- real SQL aliases are rarely the bare word "week", more often
# something like "week_start_date" or "month_bucket".
_DATE_LIKE_SUBSTRINGS = ("date", "day", "week", "month", "quarter", "year", "period", "timestamp")


def select_chart(columns: list[str], rows: list[dict[str, Any]]) -> tuple[str | None, ChartData | None]:
    """Returns (chart_type, chart_data) matching one of the dashboard's
    existing chart components, or (None, None) if there's nothing to show."""
    if not rows:
        return None, None

    column_set = set(columns)

    # A single row with at most one real value beside its label reads
    # better as one big number than as a one-bar bar chart.
    if len(rows) == 1 and len(columns) <= 2:
        return "stat", _as_stat(columns, rows[0])

    # Sentiment split three ways is exactly what the diverging bar chart
    # (used elsewhere on the dashboard) was built to show -- but only if
    # there's one row per category. A comparison question ("... by week")
    # can return the same category more than once (once per week), and
    # none of these chart components can show a third dimension at all --
    # forcing that into a chart built for one row per label draws multiple
    # overlapping bars at the same position, which is worse than no chart.
    if {"negative", "neutral", "positive"} <= column_set:
        label_column = next((c for c in columns if c not in {"negative", "neutral", "positive"}), columns[0])
        if _has_duplicate_labels(label_column, rows):
            return None, None
        return "diverging_bar", _as_diverging_bar(columns, rows)

    # A date-shaped column means the question was about change over time --
    # but only if there's one row per date. A repeated date means there's
    # another dimension (e.g. source, category) splitting each date into
    # multiple rows, which a single line can't show without silently
    # picking one of them and dropping the rest.
    date_column = _first_matching(columns, ("date", "day", "week", "month", "timestamp"))
    if date_column:
        if _has_duplicate_labels(date_column, rows):
            return None, None
        return "line", _as_line(date_column, columns, rows)

    # Exactly two columns, one of them literally "source" -- the donut
    # chart is specifically for the 3-way source breakdown, nothing wider.
    if "source" in column_set and len(columns) == 2:
        if _has_duplicate_labels("source", rows):
            return None, None
        return "donut", _as_donut(columns, rows)

    # Anything else: a label column paired with a number column, shown as
    # a ranked bar chart -- the default, most general shape.
    label_column, value_column = _label_and_value_columns(columns, rows)
    if not _has_duplicate_labels(label_column, rows):
        return "bar", _as_bar(columns, rows)

    # A repeated category usually means a comparison question ("... by
    # week") -- there's a second text column splitting each category into
    # multiple rows. That's not a reason to show nothing: split it into
    # one bar chart per distinct value of that column instead, so
    # "compare fees by source across these two weeks" becomes two
    # side-by-side category charts, one per week, rather than a single
    # chart with the same category drawn twice at once.
    pivot = _find_clean_pivot(columns, rows)
    if pivot:
        group_column, real_label_column = pivot
        return "grouped_bar", _as_grouped_bar(group_column, real_label_column, value_column, rows)

    # No column cleanly explains the repeats (e.g. more than one extra
    # dimension) -- decline rather than guess at a chart shape that would
    # still be misleading.
    return None, None


def _find_clean_pivot(columns: list[str], rows: list[dict[str, Any]]) -> tuple[str, str] | None:
    """When the naive label column has duplicates, works out which of the
    text-like columns is really the comparison axis (the "group", e.g. a
    handful of weeks) and which is the category axis (the real label) --
    by preferring whichever has FEWER distinct values as the group. A
    comparison naturally spans fewer groups (a few weeks) than categories
    (a dozen topics), regardless of which column the agent's SQL happened
    to list first or how either one is named. Returns (group_column,
    label_column), or None if no pairing resolves the duplicates cleanly."""
    sample = rows[0]
    # "Categorical" here means "not numeric," not "is a string" -- a
    # period column queried straight from Postgres (via session.execute,
    # not the JSON API boundary) comes back as a real datetime.datetime or
    # date object, never a str, and still needs to be a valid group/label
    # candidate.
    text_columns = [c for c in columns if not isinstance(sample[c], (int, float))]
    if len(text_columns) < 2:
        return None

    # Primary signal: fewer distinct values -> more likely the group (a
    # comparison spans a few weeks, not a dozen categories). Tie-break:
    # a date/period-shaped column name -> almost always the intended
    # comparison axis when the counts don't disambiguate on their own.
    def _looks_like_period(column: str) -> bool:
        return any(substring in column.lower() for substring in _DATE_LIKE_SUBSTRINGS)

    ranked = sorted(
        text_columns,
        key=lambda c: (len({row[c] for row in rows}), 0 if _looks_like_period(c) else 1),
    )
    for group_column in ranked:
        for label_column in text_columns:
            if label_column == group_column:
                continue
            groups: dict[Any, list] = {}
            for row in rows:
                groups.setdefault(row[group_column], []).append(row[label_column])
            if all(len(labels) == len(set(labels)) for labels in groups.values()):
                return group_column, label_column
    return None


def _has_duplicate_labels(label_column: str, rows: list[dict[str, Any]]) -> bool:
    """True if the same label value appears in more than one row -- a sign
    the result has a grouping dimension (e.g. one row per category *per
    week*) that this chart shape has no way to show, not just a
    coincidence. Rendering it anyway would draw multiple bars/slices at
    the same label, silently merging or overlapping instead of comparing."""
    labels = [row[label_column] for row in rows]
    return len(labels) != len(set(labels))


def _first_matching(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    lowered = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def _first_numeric_column(columns: list[str], exclude: str, rows: list[dict[str, Any]]) -> str:
    """The first column (other than `exclude`) whose value is actually a
    number, by looking at the first row -- picking "the next column" by
    position instead would grab whatever the agent's SQL happened to list
    next, which is just as likely to be another text column as the count."""
    sample = rows[0]
    return next(
        (c for c in columns if c != exclude and isinstance(sample[c], (int, float))),
        next(c for c in columns if c != exclude),
    )


def _label_and_value_columns(columns: list[str], rows: list[dict[str, Any]]) -> tuple[str, str]:
    """Picks a label column (the first non-numeric one -- a str, a
    datetime, whatever the database actually returned) and a number-like
    column to use as the value, by looking at the first row's actual
    values -- the real column names are never guaranteed in advance."""
    sample = rows[0]
    label_column = next((c for c in columns if not isinstance(sample[c], (int, float))), columns[0])
    value_column = _first_numeric_column(columns, label_column, rows)
    return label_column, value_column


def _as_stat(columns: list[str], row: dict[str, Any]) -> dict:
    label_column = columns[0]
    value_column = columns[1] if len(columns) > 1 else columns[0]
    return {"label": str(row[label_column]), "value": row[value_column]}


def _as_diverging_bar(columns: list[str], rows: list[dict[str, Any]]) -> list[dict]:
    sentiment_columns = {"negative", "neutral", "positive"}
    label_column = next((c for c in columns if c not in sentiment_columns), columns[0])
    return [
        {
            "category": str(row[label_column]),
            "negative": row.get("negative", 0),
            "neutral": row.get("neutral", 0),
            "positive": row.get("positive", 0),
        }
        for row in rows
    ]


def _as_line(date_column: str, columns: list[str], rows: list[dict[str, Any]]) -> list[dict]:
    value_column = _first_numeric_column(columns, date_column, rows)
    return [{"date": str(row[date_column]), "count": row[value_column]} for row in rows]


def _as_donut(columns: list[str], rows: list[dict[str, Any]]) -> list[dict]:
    value_column = _first_numeric_column(columns, "source", rows)
    return [{"source": row["source"], "count": row[value_column]} for row in rows]


def _as_bar(columns: list[str], rows: list[dict[str, Any]]) -> list[dict]:
    label_column, value_column = _label_and_value_columns(columns, rows)
    return [{"category": str(row[label_column]), "volume": row[value_column]} for row in rows]


def _as_grouped_bar(
    group_column: str, label_column: str, value_column: str, rows: list[dict[str, Any]]
) -> list[dict]:
    """One CategoryBarChart's worth of data per distinct group value, in
    the order groups first appeared -- e.g. [{"label": "2026-04-13",
    "data": [{"category": ..., "volume": ...}, ...]}, {"label":
    "2026-05-04", "data": [...]}] for a two-week comparison. The frontend
    renders each entry as its own bar chart, titled by `label`."""
    groups: dict[Any, list[dict]] = {}
    for row in rows:
        groups.setdefault(row[group_column], []).append(
            {"category": str(row[label_column]), "volume": row[value_column]}
        )
    return [{"label": str(group_value), "data": data} for group_value, data in groups.items()]
