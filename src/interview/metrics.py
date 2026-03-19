"""Prometheus metrics definitions for the interview module.

Defines counters, gauges, and histograms for tracking interview session
completion rates, implicit gap completion rates, and API request durations.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# Interview session metrics
# ---------------------------------------------------------------------------

interview_sessions_total = Counter(
    "interview_sessions_total",
    "Total number of interview sessions",
    ["status"],  # active / completed / terminated
)

interview_completion_rate = Gauge(
    "interview_completion_rate",
    "Interview session completion rate (completed / total finished)",
)

# ---------------------------------------------------------------------------
# Implicit gap metrics
# ---------------------------------------------------------------------------

implicit_gap_total = Counter(
    "implicit_gap_total",
    "Total number of implicit gaps detected",
)

implicit_gap_completed = Counter(
    "implicit_gap_completed",
    "Number of implicit gaps completed by user",
)

implicit_gap_completion_rate = Gauge(
    "implicit_gap_completion_rate",
    "Implicit gap completion rate",
)

# ---------------------------------------------------------------------------
# Request duration histogram
# ---------------------------------------------------------------------------

interview_request_duration = Histogram(
    "interview_request_duration_seconds",
    "Interview API request duration in seconds",
    ["endpoint", "method"],
)


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------


def report_session_completed(
    session_id: str,
    gaps_detected: int,
    gaps_completed: int,
) -> None:
    """Update all relevant metrics when an interview session completes.

    Parameters
    ----------
    session_id:
        Identifier of the completed session (for future logging/tracing).
    gaps_detected:
        Number of implicit gaps detected during the session.
    gaps_completed:
        Number of implicit gaps the user successfully completed.
    """
    # 1. Increment the completed-session counter.
    interview_sessions_total.labels(status="completed").inc()

    # 2. Recalculate interview completion rate.
    #    rate = completed / (completed + terminated)
    completed = interview_sessions_total.labels(status="completed")._value.get()
    terminated = interview_sessions_total.labels(status="terminated")._value.get()
    total_finished = completed + terminated
    if total_finished > 0:
        interview_completion_rate.set(completed / total_finished)

    # 3. Update implicit-gap counters.
    if gaps_detected > 0:
        implicit_gap_total.inc(gaps_detected)
    if gaps_completed > 0:
        implicit_gap_completed.inc(gaps_completed)

    # 4. Recalculate implicit-gap completion rate.
    total_gaps = implicit_gap_total._value.get()
    done_gaps = implicit_gap_completed._value.get()
    if total_gaps > 0:
        implicit_gap_completion_rate.set(done_gaps / total_gaps)
    else:
        implicit_gap_completion_rate.set(0.0)
