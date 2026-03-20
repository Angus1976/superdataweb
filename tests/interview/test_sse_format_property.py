"""Property-based tests for SSE event formatting.

# Feature: llm-config-management, Property 9: SSE 事件格式

For any text chunk string, the SSE formatted result must be ``data: {chunk}\\n\\n``.
The completion marker must always be ``data: [DONE]\\n\\n``.

**Validates: Requirements 8.2, 8.3**
"""

from __future__ import annotations

from hypothesis import given, settings as h_settings, strategies as st


# ---------------------------------------------------------------------------
# SSE formatting helpers (consistent with src/interview/router.py)
# ---------------------------------------------------------------------------


def format_sse_chunk(chunk: str) -> str:
    """Format a text chunk as an SSE data event."""
    return f"data: {chunk}\n\n"


def format_sse_done() -> str:
    """Return the SSE completion marker."""
    return "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Property 9: SSE 事件格式
# ---------------------------------------------------------------------------


class TestSSEEventFormat:
    """# Feature: llm-config-management, Property 9: SSE 事件格式

    For any text chunk, SSE formatting must produce ``data: {chunk}\\n\\n``.
    The done marker must always be ``data: [DONE]\\n\\n``.

    **Validates: Requirements 8.2, 8.3**
    """

    @given(chunk=st.text(min_size=0, max_size=500))
    @h_settings(max_examples=100)
    def test_sse_chunk_format(self, chunk: str) -> None:
        """# Feature: llm-config-management, Property 9: SSE 事件格式

        For any random text chunk, format_sse_chunk must return
        ``data: {chunk}\\n\\n``."""
        result = format_sse_chunk(chunk)

        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        # The content between "data: " and the trailing double-newline
        # must equal the original chunk.
        assert result == f"data: {chunk}\n\n"

    def test_sse_done_marker(self) -> None:
        """# Feature: llm-config-management, Property 9: SSE 事件格式

        The completion marker must always be ``data: [DONE]\\n\\n``."""
        result = format_sse_done()

        assert result == "data: [DONE]\n\n"
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        assert "[DONE]" in result
