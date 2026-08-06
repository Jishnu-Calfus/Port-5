"""
Unit tests for chart selection. No DB, no LLM -- select_chart() is a pure
function over plain column names and row dicts.
"""
from datetime import datetime, timezone

from backend.agent.chart_selector import select_chart


def test_empty_rows_returns_nothing():
    assert select_chart(["category", "count"], []) == (None, None)


def test_single_row_two_columns_is_a_stat():
    chart_type, data = select_chart(["total", "count"], [{"total": "all", "count": 403}])
    assert chart_type == "stat"
    assert data == {"label": "all", "value": 403}


def test_sentiment_triple_is_a_diverging_bar_regardless_of_column_order():
    columns = ["category", "positive", "negative", "neutral"]
    rows = [{"category": "Fees & Pricing", "negative": 5, "neutral": 1, "positive": 2}]
    chart_type, data = select_chart(columns, rows)
    assert chart_type == "diverging_bar"
    assert data == [{"category": "Fees & Pricing", "negative": 5, "neutral": 1, "positive": 2}]


def test_a_date_column_is_a_line_chart_even_if_not_named_date():
    columns = ["week", "n"]
    rows = [{"week": "2026-04-27", "n": 21}, {"week": "2026-05-04", "n": 15}]
    chart_type, data = select_chart(columns, rows)
    assert chart_type == "line"
    assert data == [{"date": "2026-04-27", "count": 21}, {"date": "2026-05-04", "count": 15}]


def test_source_plus_one_count_is_a_donut():
    columns = ["source", "total"]
    rows = [{"source": "Reviews", "total": 200}, {"source": "Tickets", "total": 100}]
    chart_type, data = select_chart(columns, rows)
    assert chart_type == "donut"
    assert data == [{"source": "Reviews", "count": 200}, {"source": "Tickets", "count": 100}]


def test_default_case_is_a_bar_chart_using_whatever_the_llm_named_the_columns():
    # The LLM's SQL aliased things as "cat" and "n" -- neither matches a
    # known name, so this must fall through to the generic bar case and
    # still pick the right column by looking at the actual value types.
    columns = ["cat", "n"]
    rows = [{"cat": "Fraud & Security", "n": 12}, {"cat": "Disputes & Refunds", "n": 8}]
    chart_type, data = select_chart(columns, rows)
    assert chart_type == "bar"
    assert data == [
        {"category": "Fraud & Security", "volume": 12},
        {"category": "Disputes & Refunds", "volume": 8},
    ]


def test_bar_chart_picks_the_label_column_even_when_it_is_not_first():
    # Numeric column listed before the text column, and more than one row
    # (so this doesn't hit the single-row "stat" case) -- must still find
    # the right label by value type, not just assume the first column is it.
    columns = ["n", "cat"]
    rows = [{"n": 5, "cat": "Usability & UX"}, {"n": 3, "cat": "Feature Requests"}]
    chart_type, data = select_chart(columns, rows)
    assert chart_type == "bar"
    assert data == [
        {"category": "Usability & UX", "volume": 5},
        {"category": "Feature Requests", "volume": 3},
    ]


def test_a_comparison_query_with_a_repeated_category_becomes_a_grouped_bar():
    # "compare category feedback for week A vs week B" naturally produces
    # one row per (week, category) pair -- the same category appears
    # multiple times. No single existing chart can show a third dimension
    # at once, but a clean pivot exists (one row per category per week),
    # so this should split into one bar chart per week rather than either
    # drawing overlapping bars (the original bug) or showing nothing.
    columns = ["week_start_date", "category_name", "feedback_count"]
    rows = [
        {"week_start_date": "2026-04-13", "category_name": "Account Access & Freezes", "feedback_count": 3},
        {"week_start_date": "2026-05-04", "category_name": "Account Access & Freezes", "feedback_count": 2},
        {"week_start_date": "2026-04-13", "category_name": "Transfers & Payments", "feedback_count": 1},
        {"week_start_date": "2026-05-04", "category_name": "Transfers & Payments", "feedback_count": 6},
    ]
    chart_type, data = select_chart(columns, rows)
    assert chart_type == "grouped_bar"
    assert data == [
        {
            "label": "2026-04-13",
            "data": [
                {"category": "Account Access & Freezes", "volume": 3},
                {"category": "Transfers & Payments", "volume": 1},
            ],
        },
        {
            "label": "2026-05-04",
            "data": [
                {"category": "Account Access & Freezes", "volume": 2},
                {"category": "Transfers & Payments", "volume": 6},
            ],
        },
    ]


def test_a_comparison_query_works_when_the_group_column_is_a_real_datetime_not_a_string():
    # Regression test: querying Postgres directly via session.execute()
    # (not through the JSON API boundary) returns native datetime.datetime
    # objects for timestamp columns, never strings. The pivot-finding
    # logic must treat "categorical" as "not numeric," not "is a str", or
    # it silently excludes the period column and never finds the pivot.
    week1 = datetime(2026, 4, 13, tzinfo=timezone.utc)
    week2 = datetime(2026, 5, 4, tzinfo=timezone.utc)
    columns = ["category_name", "week_start", "feedback_count"]
    rows = [
        {"category_name": "Account Access & Freezes", "week_start": week1, "feedback_count": 4},
        {"category_name": "Transfers & Payments", "week_start": week1, "feedback_count": 1},
        {"category_name": "Account Access & Freezes", "week_start": week2, "feedback_count": 3},
        {"category_name": "Transfers & Payments", "week_start": week2, "feedback_count": 7},
    ]
    chart_type, data = select_chart(columns, rows)
    assert chart_type == "grouped_bar"
    assert len(data) == 2
    assert data[0]["label"] == str(week1)
    assert data[0]["data"] == [
        {"category": "Account Access & Freezes", "volume": 4},
        {"category": "Transfers & Payments", "volume": 1},
    ]
    # Category values must come back as plain strings, not raw datetimes,
    # or FastAPI/Pydantic has nothing telling it how to serialize them.
    assert all(isinstance(row["category"], str) for group in data for row in group["data"])


def test_a_repeated_category_with_no_clean_pivot_still_declines():
    # Two categories repeat, but no single other column explains it (each
    # "extra" column still has its own duplicates within any split) --
    # there's no clean pivot to fall back to, so this must still decline
    # rather than guess at a grouping that doesn't actually resolve the
    # repeats.
    columns = ["category", "region", "count"]
    rows = [
        {"category": "Fees & Pricing", "region": "US", "count": 3},
        {"category": "Fees & Pricing", "region": "US", "count": 5},
        {"category": "Fees & Pricing", "region": "EU", "count": 2},
    ]
    assert select_chart(columns, rows) == (None, None)


def test_a_repeated_source_also_declines_to_chart_as_a_donut():
    columns = ["source", "count"]
    rows = [{"source": "Reviews", "count": 5}, {"source": "Reviews", "count": 8}]
    assert select_chart(columns, rows) == (None, None)


def test_a_repeated_date_declines_to_chart_as_a_line():
    # Same date appearing twice means another dimension (here, source) is
    # splitting each date into multiple rows -- a single line can't show
    # that without silently dropping one of them.
    columns = ["week", "source", "count"]
    rows = [
        {"week": "2026-04-13", "source": "Reviews", "count": 5},
        {"week": "2026-04-13", "source": "Tickets", "count": 3},
    ]
    assert select_chart(columns, rows) == (None, None)


def test_line_chart_picks_the_numeric_column_even_when_a_text_column_comes_first():
    # Regression test: with more than one non-date column, the value must
    # be picked by checking it's actually numeric, not just "whichever
    # column isn't the date" -- "source" here is a string and must not be
    # mistaken for the count.
    columns = ["source", "week", "count"]
    rows = [
        {"source": "Reviews", "week": "2026-04-13", "count": 5},
        {"source": "Reviews", "week": "2026-05-04", "count": 8},
    ]
    chart_type, data = select_chart(columns, rows)
    assert chart_type == "line"
    assert data == [{"date": "2026-04-13", "count": 5}, {"date": "2026-05-04", "count": 8}]
