"""Unit tests for PromptManager — assemble, parse, validate_length.

**Validates: Requirements 4.2, 4.3, 4.5**
"""

from __future__ import annotations

from src.interview.prompt_manager import PromptManager, StructuredPrompt


_pm = PromptManager()


class TestAssemble:
    """assemble joins four sections with ## headers and double-newline separators."""

    def test_basic_assembly(self) -> None:
        prompt = StructuredPrompt(
            role_definition="你是一名资深访谈员",
            task_description="对用户进行深度访谈",
            behavior_rules="保持礼貌",
            output_format="JSON 格式输出",
        )
        result = _pm.assemble(prompt)
        expected = (
            "## 角色定义\n你是一名资深访谈员\n\n"
            "## 任务描述\n对用户进行深度访谈\n\n"
            "## 行为规则\n保持礼貌\n\n"
            "## 输出格式\nJSON 格式输出"
        )
        assert result == expected

    def test_empty_sections(self) -> None:
        prompt = StructuredPrompt()
        result = _pm.assemble(prompt)
        assert "## 角色定义\n" in result
        assert "## 任务描述\n" in result
        assert "## 行为规则\n" in result
        assert "## 输出格式\n" in result


class TestParse:
    """parse splits a well-formed system_prompt back into four sections."""

    def test_roundtrip(self) -> None:
        original = StructuredPrompt(
            role_definition="角色A",
            task_description="任务B",
            behavior_rules="规则C",
            output_format="格式D",
        )
        assembled = _pm.assemble(original)
        parsed = _pm.parse(assembled)
        assert parsed == original

    def test_fallback_on_malformed_input(self) -> None:
        raw = "这是一段没有分区标记的普通文本"
        parsed = _pm.parse(raw)
        assert parsed.role_definition == raw
        assert parsed.task_description == ""
        assert parsed.behavior_rules == ""
        assert parsed.output_format == ""

    def test_fallback_on_empty_string(self) -> None:
        parsed = _pm.parse("")
        assert parsed.role_definition == ""
        assert parsed.task_description == ""
        assert parsed.behavior_rules == ""
        assert parsed.output_format == ""


class TestValidateLength:
    """validate_length returns True iff len(system_prompt) <= 8000."""

    def test_within_limit(self) -> None:
        assert _pm.validate_length("x" * 8000) is True

    def test_at_boundary(self) -> None:
        assert _pm.validate_length("x" * 8000) is True
        assert _pm.validate_length("x" * 8001) is False

    def test_empty(self) -> None:
        assert _pm.validate_length("") is True


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------

from hypothesis import given, settings as h_settings, strategies as st

# Section markers that generated strings must NOT contain
_SECTION_MARKERS = ("## 角色定义", "## 任务描述", "## 行为规则", "## 输出格式")


def _no_markers(s: str) -> bool:
    """Return True if *s* does not contain any section marker."""
    return all(marker not in s for marker in _SECTION_MARKERS)


# Strategy: arbitrary text that never contains a section marker.
# We filter rather than try to construct marker-free text because the markers
# are multi-byte CJK strings and extremely unlikely in random ASCII/unicode.
_marker_free_text = st.text(max_size=200).filter(_no_markers)


class TestAssembleParseRoundtripProperty:
    """# Feature: llm-config-management, Property 4: 提示词组装/解析往返一致性

    For any four marker-free section strings, assemble → parse must return
    the original four sections unchanged.

    **Validates: Requirements 4.2, 4.3**
    """

    @given(
        role=_marker_free_text,
        task=_marker_free_text,
        rules=_marker_free_text,
        fmt=_marker_free_text,
    )
    @h_settings(max_examples=100, deadline=None)
    def test_assemble_then_parse_roundtrip(
        self, role: str, task: str, rules: str, fmt: str
    ) -> None:
        # Feature: llm-config-management, Property 4: 提示词组装/解析往返一致性
        original = StructuredPrompt(
            role_definition=role,
            task_description=task,
            behavior_rules=rules,
            output_format=fmt,
        )
        assembled = _pm.assemble(original)
        parsed = _pm.parse(assembled)

        assert parsed.role_definition == role
        assert parsed.task_description == task
        assert parsed.behavior_rules == rules
        assert parsed.output_format == fmt


class TestParseFallbackProperty:
    """# Feature: llm-config-management, Property 4: 提示词组装/解析往返一致性

    For any string that does NOT contain section markers, parse must place
    the entire string into role_definition with the other three fields empty.

    **Validates: Requirements 4.2, 4.3**
    """

    @given(raw=_marker_free_text)
    @h_settings(max_examples=100, deadline=None)
    def test_parse_fallback_puts_all_in_role_definition(self, raw: str) -> None:
        # Feature: llm-config-management, Property 4: 提示词组装/解析往返一致性
        parsed = _pm.parse(raw)

        assert parsed.role_definition == raw
        assert parsed.task_description == ""
        assert parsed.behavior_rules == ""
        assert parsed.output_format == ""


class TestValidateLengthProperty:
    """# Feature: llm-config-management, Property 5: 提示词长度校验

    For any string, validate_length returns True iff len(string) <= 8000.

    **Validates: Requirements 4.5**
    """

    @given(text=st.text(min_size=0, max_size=16000))
    @h_settings(max_examples=100, deadline=None)
    def test_validate_length_matches_len_check(self, text: str) -> None:
        # Feature: llm-config-management, Property 5: 提示词长度校验
        assert _pm.validate_length(text) == (len(text) <= 8000)
