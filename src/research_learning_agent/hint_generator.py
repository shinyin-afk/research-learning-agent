"""
Hint Generator — generates calibrated Socratic hints for programming questions.
NEVER gives the full answer. Always guides the learner to discover it.
"""
from __future__ import annotations

import json
import re

from .programming_schemas import HintRequest, HintResponse, HintLevel, ProgrammingCapability, ProgrammingTopic
from .schemas import LLMMessage
from .llm_client import LLMClient
from .logging_utils import get_logger

logger = get_logger("HintGenerator")

HINT_SYSTEM_PROMPT = """
You are a programming mentor. Your ONLY job is to give HINTS — NEVER full solutions.

RULE: Never write complete working code that solves the problem. Short illustrative 
fragments (1-3 lines unrelated to their exact problem) are allowed at structural+ levels.

Use the Socratic method — ask questions that lead learners to discover answers.

HINT LEVELS (follow exactly):
- conceptual:    Name the core concept. Ask ONE connecting question. NO code.
- directional:   Point toward the right approach. Name a function/structure if helpful.
                 Ask what they think the first step is.
- structural:    Provide pseudocode skeleton with blanks. Ask which part is unclear.
- targeted:      Address the exact stuck point. 1-3 line illustrative snippet OK.
- near_solution: Strong nudge — leave final assembly to learner. Pattern/template OK.

TONE by capability:
- novice: Warm, patient, analogies, no jargon.
- developing: Friendly, introduce terms gradually.
- competent: Collegial, correct vocabulary.
- proficient: Peer-like, direct.
- expert: Terse, peer, edge cases / trade-offs.

Always end with a Socratic question. Always include brief genuine encouragement.

Return ONLY valid JSON:
{
  "hint_level": "conceptual|directional|structural|targeted|near_solution",
  "capability_used": "novice|developing|competent|proficient|expert",
  "topic": "syntax|data_structures|algorithms|debugging|design|libraries|general",
  "hint": "<hint text, markdown OK>",
  "socratic_question": "<ONE question>",
  "concept_to_review": "<concept name or null>",
  "analogy": "<analogy or null>",
  "suggest_next_hint": false,
  "encouragement": "<short encouragement>"
}
"""


def _build_user_prompt(req: HintRequest) -> str:
    parts = [f"Learner question:\n{req.question}"]
    if req.code_snippet:
        parts.append(f"\nCode written so far:\n```\n{req.code_snippet}\n```")
    if req.error_message:
        parts.append(f"\nError message:\n```\n{req.error_message}\n```")
    parts.append(
        f"\nCalibration:\n- capability: {req.capability.value}\n"
        f"- hint_level: {req.hint_level.value}\n- topic: {req.topic.value}"
    )
    if req.session_context:
        ctx = "\n".join(
            f"[{t.get('role','')}]: {str(t.get('content',''))[:300]}"
            for t in req.session_context[-3:]
        )
        parts.append(f"\nRecent chat:\n{ctx}")
    return "\n".join(parts)


class HintGenerator:
    def __init__(self) -> None:
        self._llm: LLMClient | None = None

    @property
    def llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def generate(self, req: HintRequest) -> HintResponse:
        messages = [
            LLMMessage(role="system", content=HINT_SYSTEM_PROMPT),
            LLMMessage(role="user", content=_build_user_prompt(req)),
        ]
        raw = self.llm.chat(messages)
        return self._parse(raw, req)

    def _parse(self, raw: str, req: HintRequest) -> HintResponse:
        text = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("HintGenerator JSON parse failed, using raw text")
            return HintResponse(
                hint_level=req.hint_level, capability_used=req.capability, topic=req.topic,
                hint=raw, socratic_question="What do you think the next step might be?",
                encouragement="Keep going — you're making progress!",
            )
        return HintResponse(
            hint_level=HintLevel(data.get("hint_level", req.hint_level.value)),
            capability_used=ProgrammingCapability(data.get("capability_used", req.capability.value)),
            topic=ProgrammingTopic(data.get("topic", req.topic.value)),
            hint=data.get("hint", ""),
            socratic_question=data.get("socratic_question"),
            concept_to_review=data.get("concept_to_review"),
            analogy=data.get("analogy"),
            suggest_next_hint=bool(data.get("suggest_next_hint", False)),
            encouragement=data.get("encouragement"),
        )
