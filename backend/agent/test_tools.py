"""
Tests for the actual query-execution logic behind the run_sql tool. These
use the real read-only database session (backend.db.ROSessionLocal) -- the
point is to prove the read-only role really is read-only from inside this
code path, not just to check that a mock returns what a mock was told to
return.

Requires Postgres running locally with the pulseai_ro role already created
(see README) -- these are integration tests, not pure-function tests, which
is why they live separately from test_sql_gateway.py and test_chart_selector.py.
"""
import pytest

from backend.agent.tools import execute_sql
from backend.db import ROSessionLocal


@pytest.fixture
def ro_session():
    session = ROSessionLocal()
    yield session
    session.close()


def test_select_returns_real_rows(ro_session):
    result = execute_sql(ro_session, "SELECT count(*) AS total FROM fact_feedback")
    assert result.error is None
    assert result.columns == ["total"]
    assert result.row_count == 1
    assert result.rows[0]["total"] >= 0


def test_a_write_attempt_is_rejected_by_postgres_itself(ro_session):
    # This is the actual safety guarantee, proven end to end: even though
    # nothing in this function's own code checks for write statements, the
    # database role itself refuses the write.
    result = execute_sql(ro_session, "INSERT INTO dim_source (name) VALUES ('should not work')")
    assert result.error is not None
    assert "permission denied" in result.error.lower()
    assert result.row_count == 0


def test_session_recovers_after_a_rejected_write_and_can_run_a_later_query(ro_session):
    # Without the rollback in execute_sql, a failed statement would leave
    # the session's transaction stuck, and this second query would fail too
    # -- even though it's a completely valid, unrelated SELECT.
    execute_sql(ro_session, "INSERT INTO dim_source (name) VALUES ('nope')")
    result = execute_sql(ro_session, "SELECT count(*) AS total FROM dim_source")
    assert result.error is None
    assert result.row_count == 1
