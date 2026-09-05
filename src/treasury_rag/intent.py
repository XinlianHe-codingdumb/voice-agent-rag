from __future__ import annotations

import re
from dataclasses import dataclass

from .long_term_memory import extract_explicit_memories, is_memory_query


CONVERSATION = "conversation"
DOCUMENT_FACT = "document_fact"
DOCUMENT_TASK = "document_task"
MEMORY = "memory"


_DOCUMENT_TASK_MARKERS = (
    "should i", "what should", "recommend", "roadmap", "study", "learn",
    "job", "career", "compare", "summarize", "summary", "chapter",
    "该看", "应该看", "学习", "找工作", "职业", "推荐", "路线", "总结",
    "比较", "章节",
)

_CONVERSATION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:hello|hi|hey|good morning|good afternoon|good evening)",
        r"(?:(?:can|could|do) you (?:hear|see|understand) me|are you (?:there|listening))",
        r"(?:thanks|thank you|thank you very much)",
        r"(?:who are you|what can you do|how are you)",
        r"(?:what did i (?:just )?ask(?: you)?|what were we (?:just )?(?:talking|speaking) about)",
        r"(?:repeat (?:that|your answer)|say that again)",
        r"(?:ok|okay|yes|yeah|yep|sure|all right|alright)",
        r"(?:你好|您好|早上好|下午好|晚上好|嗨)",
        r"(?:你能听(?:到|见)我(?:说话)?吗|听得到吗|你在吗|你在听吗)",
        r"(?:谢谢|感谢|好的|好啊|可以|没问题|嗯|嗯嗯)",
        r"(?:你是谁|你能做什么|你怎么样)",
        r"(?:我刚才问了什么|我刚刚问了什么|我们刚才聊了什么|我们刚刚在聊什么)",
        r"(?:再说一遍|重复一下)",
    )
)


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    reason: str

    @property
    def requires_documents(self) -> bool:
        return self.intent in {DOCUMENT_FACT, DOCUMENT_TASK}

    @property
    def uses_agent_harness(self) -> bool:
        return self.intent == DOCUMENT_TASK

    def as_dict(self) -> dict[str, object]:
        return {
            "intent": self.intent,
            "reason": self.reason,
            "requires_documents": self.requires_documents,
            "uses_agent_harness": self.uses_agent_harness,
        }


def classify_intent(text: str) -> IntentDecision:
    """Fast, auditable routing shared by text, push-to-talk, and Realtime."""
    normalized = re.sub(r"\s+", " ", text.casefold()).strip(
        " \t\r\n.,!?;:。！？；：\"'"
    )
    if extract_explicit_memories(text):
        return IntentDecision(MEMORY, "explicit-memory-write")
    if is_memory_query(text):
        return IntentDecision(MEMORY, "explicit-memory-read")
    if any(pattern.fullmatch(normalized) for pattern in _CONVERSATION_PATTERNS):
        return IntentDecision(CONVERSATION, "conversation-pattern")
    if any(marker in normalized for marker in _DOCUMENT_TASK_MARKERS):
        return IntentDecision(DOCUMENT_TASK, "document-task-marker")
    return IntentDecision(DOCUMENT_FACT, "document-grounded-default")
