"""Backward-compatible exports for prompt templates.

New prompt modules live in :mod:`prompt_templates`, grouped by tool.
"""

from prompt_templates.detector import DETECTOR_SYSTEM_PROMPT, format_detector_prompt
from prompt_templates.humanizer import SYSTEM_PROMPT, format_humanize_prompt
from prompt_templates.paraphraser import PARAPHRASER_SYSTEM_PROMPT, format_paraphraser_prompt

__all__ = [
    "SYSTEM_PROMPT",
    "format_humanize_prompt",
    "DETECTOR_SYSTEM_PROMPT",
    "format_detector_prompt",
    "PARAPHRASER_SYSTEM_PROMPT",
    "format_paraphraser_prompt",
]
