"""结构化提示词管理：组装、解析、校验。

提供 StructuredPrompt 数据类和 PromptManager 工具类，用于将四分区
（角色定义、任务描述、行为规则、输出格式）拼接为完整 system_prompt，
以及将完整 system_prompt 解析回四分区。

**Validates: Requirements 4.2, 4.3, 4.5**
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Section headers used for assembly and parsing
_HEADERS = ("## 角色定义", "## 任务描述", "## 行为规则", "## 输出格式")

_MAX_LENGTH = 8000


@dataclass
class StructuredPrompt:
    """四分区结构化提示词。"""

    role_definition: str = ""
    task_description: str = ""
    behavior_rules: str = ""
    output_format: str = ""


class PromptManager:
    """结构化提示词组装、解析、校验。"""

    # ------------------------------------------------------------------
    # assemble
    # ------------------------------------------------------------------

    def assemble(self, prompt: StructuredPrompt) -> str:
        """将四分区拼接为完整 system_prompt。

        格式：
            ## 角色定义
            {role_definition}

            ## 任务描述
            {task_description}

            ## 行为规则
            {behavior_rules}

            ## 输出格式
            {output_format}
        """
        sections = [
            f"## 角色定义\n{prompt.role_definition}",
            f"## 任务描述\n{prompt.task_description}",
            f"## 行为规则\n{prompt.behavior_rules}",
            f"## 输出格式\n{prompt.output_format}",
        ]
        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------

    def parse(self, system_prompt: str) -> StructuredPrompt:
        """将完整 system_prompt 解析回四分区。

        解析失败时（缺少任一分区标记）将完整内容填入 role_definition，
        其余字段为空字符串。
        """
        # Build a regex that captures content between the four headers.
        # Each header must appear in order; content is everything between
        # the current header line and the next header (or end of string).
        pattern = (
            r"^## 角色定义\n(.*?)"
            r"\n\n## 任务描述\n(.*?)"
            r"\n\n## 行为规则\n(.*?)"
            r"\n\n## 输出格式\n(.*)$"
        )
        match = re.match(pattern, system_prompt, re.DOTALL)

        if match:
            return StructuredPrompt(
                role_definition=match.group(1),
                task_description=match.group(2),
                behavior_rules=match.group(3),
                output_format=match.group(4),
            )

        # Fallback: put everything into role_definition
        return StructuredPrompt(
            role_definition=system_prompt,
            task_description="",
            behavior_rules="",
            output_format="",
        )

    # ------------------------------------------------------------------
    # validate_length
    # ------------------------------------------------------------------

    def validate_length(self, system_prompt: str) -> bool:
        """校验总长度不超过 8000 字符。"""
        return len(system_prompt) <= _MAX_LENGTH
