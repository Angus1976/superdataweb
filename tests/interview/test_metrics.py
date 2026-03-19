"""Unit tests for interview Prometheus metrics."""

from __future__ import annotations

import pytest
from prometheus_client import REGISTRY, CollectorRegistry

from src.interview import metrics as m


@pytest.fixture(autouse=True)
def _reset_metrics():
    """Reset all interview counters/gauges before each test.

    prometheus_client metrics are global singletons, so we need to reset
    their internal values between tests to avoid cross-test contamination.
    """
    # Reset counters (label-based and plain).
    for status in ("active", "completed", "terminated"):
        m.interview_sessions_total.labels(status=status)._value.set(0)
    m.implicit_gap_total._value.set(0)
    m.implicit_gap_completed._value.set(0)

    # Reset gauges.
    m.interview_completion_rate.set(0.0)
    m.implicit_gap_completion_rate.set(0.0)

    yield


# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------


class TestMetricDefinitions:
    """Verify that all required metrics are defined with correct types."""

    def test_interview_sessions_total_is_counter(self):
        assert m.interview_sessions_total._type == "counter"

    def test_interview_sessions_total_has_status_label(self):
        # Accessing a labelled child should work without error.
        child = m.interview_sessions_total.labels(status="active")
        assert child is not None

    def test_interview_completion_rate_is_gauge(self):
        assert m.interview_completion_rate._type == "gauge"

    def test_implicit_gap_total_is_counter(self):
        assert m.implicit_gap_total._type == "counter"

    def test_implicit_gap_completed_is_counter(self):
        assert m.implicit_gap_completed._type == "counter"

    def test_implicit_gap_completion_rate_is_gauge(self):
        assert m.implicit_gap_completion_rate._type == "gauge"

    def test_request_duration_is_histogram(self):
        assert m.interview_request_duration._type == "histogram"

    def test_request_duration_has_endpoint_method_labels(self):
        child = m.interview_request_duration.labels(
            endpoint="/api/interview/sessions", method="POST"
        )
        assert child is not None


# ---------------------------------------------------------------------------
# report_session_completed
# ---------------------------------------------------------------------------


class TestReportSessionCompleted:
    """Tests for the report_session_completed helper."""

    def test_increments_completed_counter(self):
        m.report_session_completed("s1", gaps_detected=0, gaps_completed=0)
        val = m.interview_sessions_total.labels(status="completed")._value.get()
        assert val == 1.0

    def test_completion_rate_after_one_session(self):
        m.report_session_completed("s1", gaps_detected=0, gaps_completed=0)
        # 1 completed, 0 terminated → rate = 1.0
        assert m.interview_completion_rate._value.get() == 1.0

    def test_completion_rate_with_terminated_sessions(self):
        # Simulate 2 terminated sessions first.
        m.interview_sessions_total.labels(status="terminated").inc(2)
        m.report_session_completed("s1", gaps_detected=0, gaps_completed=0)
        # 1 completed / (1 + 2) = 1/3
        rate = m.interview_completion_rate._value.get()
        assert abs(rate - 1.0 / 3.0) < 1e-9

    def test_implicit_gap_counters_updated(self):
        m.report_session_completed("s1", gaps_detected=5, gaps_completed=3)
        assert m.implicit_gap_total._value.get() == 5.0
        assert m.implicit_gap_completed._value.get() == 3.0

    def test_implicit_gap_completion_rate(self):
        m.report_session_completed("s1", gaps_detected=10, gaps_completed=7)
        rate = m.implicit_gap_completion_rate._value.get()
        assert abs(rate - 0.7) < 1e-9

    def test_gap_rate_zero_when_no_gaps(self):
        m.report_session_completed("s1", gaps_detected=0, gaps_completed=0)
        assert m.implicit_gap_completion_rate._value.get() == 0.0

    def test_multiple_sessions_accumulate(self):
        m.report_session_completed("s1", gaps_detected=4, gaps_completed=2)
        m.report_session_completed("s2", gaps_detected=6, gaps_completed=5)
        # Total gaps: 10, completed: 7 → rate = 0.7
        assert m.implicit_gap_total._value.get() == 10.0
        assert m.implicit_gap_completed._value.get() == 7.0
        assert abs(m.implicit_gap_completion_rate._value.get() - 0.7) < 1e-9
        # 2 completed, 0 terminated → completion rate = 1.0
        assert m.interview_completion_rate._value.get() == 1.0
