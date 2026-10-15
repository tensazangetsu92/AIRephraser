"""Backward-compatible exports for prompt templates.

New prompt modules live in :mod:`prompt_templates`, grouped by tool.
"""

from prompt_templates.humanizer import SYSTEM_PROMPT, format_humanize_prompt
from prompt_templates.paraphraser import PARAPHRASER_SYSTEM_PROMPT, format_paraphraser_prompt
from prompt_templates.study_work import (
    STUDY_WORK_DOCX_SYSTEM_PROMPT,
    STUDY_WORK_DOCX_BATCH_PROMPT_TEMPLATE,
    STUDY_WORK_HUMANIZE_PROMPT_TEMPLATE,
    format_study_work_docx_batch_prompt,
    format_study_work_humanize_prompt,
)

__all__ = [
    "SYSTEM_PROMPT",
    "format_humanize_prompt",
    "PARAPHRASER_SYSTEM_PROMPT",
    "format_paraphraser_prompt",
    "STUDY_WORK_DOCX_SYSTEM_PROMPT",
    "STUDY_WORK_DOCX_BATCH_PROMPT_TEMPLATE",
    "STUDY_WORK_HUMANIZE_PROMPT_TEMPLATE",
    "format_study_work_docx_batch_prompt",
    "format_study_work_humanize_prompt",
]
