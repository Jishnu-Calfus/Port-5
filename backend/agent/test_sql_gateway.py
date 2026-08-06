"""
Unit tests for the SQL safety gateway. This file needs no database and no
LLM -- validate_and_rewrite() is a pure function, so every case here is just
a string in, a string (or an exception) out. This is deliberately the most
thoroughly tested file in the whole feature, since it's the actual security
boundary: everything else assumes this gateway does its job correctly.
"""
import pytest

from backend.agent.sql_gateway import SQLValidationError, validate_and_rewrite


# --- queries that must be rejected -------------------------------------------

def test_rejects_multiple_statements():
    with pytest.raises(SQLValidationError):
        validate_and_rewrite("SELECT 1; DROP TABLE fact_feedback;")


def test_rejects_non_select_statement():
    with pytest.raises(SQLValidationError):
        validate_and_rewrite("DELETE FROM fact_feedback")


def test_rejects_unknown_table():
    with pytest.raises(SQLValidationError):
        validate_and_rewrite("SELECT * FROM pg_shadow")


def test_rejects_unknown_column():
    with pytest.raises(SQLValidationError):
        validate_and_rewrite("SELECT fact_feedback.does_not_exist FROM fact_feedback")


def test_rejects_ambiguous_column_across_join():
    # "id" exists on both fact_feedback and dim_category -- unqualified, it
    # cannot be resolved to either one, and must fail closed, not guess.
    with pytest.raises(SQLValidationError):
        validate_and_rewrite("SELECT id FROM fact_feedback, dim_category")


def test_rejects_dangerous_function():
    with pytest.raises(SQLValidationError):
        validate_and_rewrite("SELECT pg_read_file('/etc/passwd')")


def test_rejects_write_smuggled_inside_a_cte():
    # The whole statement still parses as a single top-level SELECT, so the
    # "exactly one statement" check alone would not catch this -- it needs
    # its own explicit check for a nested write node anywhere in the tree.
    sql = (
        "WITH x AS (DELETE FROM fact_feedback RETURNING id) "
        "SELECT id FROM x"
    )
    with pytest.raises(SQLValidationError):
        validate_and_rewrite(sql)


def test_rejects_comment_smuggling_a_second_statement():
    with pytest.raises(SQLValidationError):
        validate_and_rewrite("SELECT 1 -- ; DROP TABLE fact_feedback;\n; DROP TABLE fact_feedback;")


# --- queries that must be allowed, and rewritten correctly -------------------

def test_allows_simple_select():
    result = validate_and_rewrite("SELECT count(*) FROM fact_feedback")
    assert "count" in result.lower()


def test_allows_the_multi_label_category_join():
    sql = (
        "SELECT dim_category.name, count(*) "
        "FROM fact_feedback "
        "JOIN fact_feedback_category ON fact_feedback.id = fact_feedback_category.feedback_id "
        "JOIN dim_category ON fact_feedback_category.category_id = dim_category.id "
        "WHERE dim_category.name = 'Fees & Pricing' "
        "GROUP BY dim_category.name"
    )
    result = validate_and_rewrite(sql)
    assert "dim_category" in result
    assert "LIMIT" in result.upper()  # no LIMIT was given -- one must be added


def test_adds_a_default_limit_when_none_given():
    result = validate_and_rewrite("SELECT id FROM fact_feedback")
    assert "LIMIT 500" in result.upper()


def test_clamps_an_oversized_limit_down_to_the_max():
    result = validate_and_rewrite("SELECT id FROM fact_feedback LIMIT 100000")
    assert "LIMIT 500" in result.upper()
    assert "100000" not in result


def test_leaves_a_reasonable_limit_untouched():
    result = validate_and_rewrite("SELECT id FROM fact_feedback LIMIT 10")
    assert "LIMIT 10" in result.upper()


def test_rejection_reason_is_readable_not_a_raw_stack_trace():
    with pytest.raises(SQLValidationError) as exc_info:
        validate_and_rewrite("DROP TABLE fact_feedback")
    # The message is what gets fed back to the agent to self-correct with --
    # it needs to read as an instruction, not an opaque error code.
    assert "SELECT" in exc_info.value.reason
