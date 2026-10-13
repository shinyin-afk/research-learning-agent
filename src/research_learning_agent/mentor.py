"""
ProgrammingMentor
=================
High-level coordinator for the hint-focused programming assistant.

Flow per learner turn:
1. Load (or create) the learner's CapabilityProfile from persistent memory.
2. Analyze the new message to update the capability gauge.
3. Calibrate the hint level from the (updated) capability.
4. Generate a Socratic hint (never a full solution) via the LLM.
5. Persist the updated profile so the next turn remembers this learner.

The mentor also tracks the learner's past prompts via CapabilityProfile.signals
and recent_topics, giving it long-term memory of what each learner has attempted.
"""
from __future__ import annotations

from typing import Any

from .programming_schemas import (
    CapabilityProfile, HintRequest, HintResponse, HintLevel,
    ProgrammingCapability, ProgrammingTopic,
)
from .capability_analyzer import CapabilityAnalyzer, infer_topic, escalate_hint
from .hint_generator import HintGenerator
from .stores.capability_store import CapabilityStore
from .logging_utils import get_logger


logger = get_logger("ProgrammingMentor")


class ProgrammingMentor:
    """Coordinates capability gauging + hint generation with persistent memory."""

    def __init__(self) -> None:
        self.analyzer = CapabilityAnalyzer()
        self.generator = HintGenerator()
        self.store = CapabilityStore()
        # In-session memory of the last hint level per user (for escalation)
        self._last_hint_level: dict[str, HintLevel] = {}
        self._session_context: dict[str, list[dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_profile(self, user_id: str = "default") -> CapabilityProfile:
        return self.store.load(user_id) or CapabilityProfile(user_id=user_id)

    def answer(
        self,
        *,
        user_id: str,
        message: str,
        code_snippet: str | None = None,
        error_message: str | None = None,
        is_followup: bool = False,
        user_responded_correctly: bool | None = None,
        self_corrected: bool = False,
    ) -> tuple[HintResponse, CapabilityProfile]:
        """Process one learner turn, return (hint, updated_profile)."""
        profile = self.get_profile(user_id)

        # Determine whether this is a continuation of the same problem
        # (i.e. the learner asked for another hint after our last one)
        prev_hint = self._last_hint_level.get(user_id)

        # 1) Update capability from this message
        profile = self.analyzer.analyze_turn(
            profile,
            user_message=message,
            user_responded_correctly=user_responded_correctly,
            needed_hint_escalation=is_followup and prev_hint is not None,
            self_corrected=self_corrected,
        )

        # 2) Infer topic
        topic = infer_topic(message)

        # 3) Calibrate hint level
        hint_level = self.analyzer.get_hint_level(
            profile,
            topic=topic,
            is_followup=is_followup,
            previous_hint_level=prev_hint,
        )

        # 4) Track session context
        ctx = self._session_context.setdefault(user_id, [])
        ctx.append({"role": "user", "content": message})
        ctx = ctx[-10:]  # keep bounded
        self._session_context[user_id] = ctx

        # 5) Build request & generate hint
        req = HintRequest(
            user_id=user_id,
            question=message,
            code_snippet=code_snippet,
            error_message=error_message,
            topic=topic,
            capability=profile.capability,
            hint_level=hint_level,
            session_context=ctx,
        )
        hint = self.generator.generate(req)

        # 6) Remember hint level + context, persist profile
        self._last_hint_level[user_id] = hint.hint_level
        ctx.append({"role": "assistant", "content": hint.hint})
        self._session_context[user_id] = ctx[-10:]
        self.store.save(profile)

        logger.info(
            "Mentor answer: user=%s cap=%s topic=%s hint=%s",
            user_id, profile.capability.value, topic.value, hint.hint_level.value,
        )
        return hint, profile

    def escalation_prompt(self, user_id: str) -> str | None:
        """Return a canned prompt if the learner wants a deeper hint."""
        level = self._last_hint_level.get(user_id)
        if level is None:
            return None
        next_level = escalate_hint(level)
        if next_level == level:
            return "You've reached the deepest hint level — try writing out what you know so far."
        return f"Okay, here's a slightly deeper hint (moving to: {next_level.value})."

    def reset_session(self, user_id: str) -> None:
        """Clear in-session context (persistent capability memory remains)."""
        self._session_context.pop(user_id, None)
        self._last_hint_level.pop(user_id, None)
