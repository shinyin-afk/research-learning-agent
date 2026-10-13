"""
Capability Analyzer
===================
Infers a learner's programming capability from their conversation history.
"""
from __future__ import annotations

import re

from .programming_schemas import (
    CapabilityProfile, CapabilitySignal,
    ProgrammingCapability, ProgrammingTopic, HintLevel,
)
from .logging_utils import get_logger

logger = get_logger("CapabilityAnalyzer")

# ---------------------------------------------------------------------------
# Regex signal detectors
# ---------------------------------------------------------------------------
_CORRECT_VOCAB = re.compile(
    r"\b(time complexity|big.?o|recursion|iteration|refactor|abstraction|"
    r"encapsulation|polymorphism|inheritance|stack|queue|heap|hash|"
    r"binary search|dynamic programming|memoiz|greedy|divide and conquer|"
    r"pointer|reference|closure|decorator|generator|async|concurrency|"
    r"race condition|deadlock|mutex|semaphore|garbage collect|"
    r"off.by.one|edge case|unit test|mock|assert)\b", re.IGNORECASE)

_CONFUSION = re.compile(
    r"\b(i don'?t understand|confused|lost|no idea|where do i start|"
    r"what does .* mean|why is this wrong|nothing works|"
    r"i tried everything|i give up|doesn'?t make sense)\b", re.IGNORECASE)

_SYNTAX_Q = re.compile(
    r"\b(how do i print|what is a variable|what is a function|"
    r"how do i loop|what is an if statement|how do i import|"
    r"what is indentation|syntax error)\b", re.IGNORECASE)

_SELF_CORRECT = re.compile(
    r"\b(actually|wait,?|i think i see|never mind|i figured|"
    r"oh i see|that makes sense now|so it'?s because)\b", re.IGNORECASE)

_DESIGN = re.compile(
    r"\b(trade.?off|better approach|more efficient|scalab|maintainabl|"
    r"design pattern|which is better|when should i use|why not use|"
    r"alternative|pros and cons)\b", re.IGNORECASE)

_DEBUG_CONTEXT = re.compile(
    r"\b(i tried|i expected|but it returns|instead of|the error says|"
    r"stack trace|traceback|line \d+|exception|runtime error)\b", re.IGNORECASE)

# Capability numeric mapping
_CAP_SCORE: dict[ProgrammingCapability, float] = {
    ProgrammingCapability.novice: 0.0,
    ProgrammingCapability.developing: 0.25,
    ProgrammingCapability.competent: 0.50,
    ProgrammingCapability.proficient: 0.75,
    ProgrammingCapability.expert: 1.00,
}
_SCORE_TO_CAP: list[tuple[float, ProgrammingCapability]] = [
    (0.10, ProgrammingCapability.novice),
    (0.35, ProgrammingCapability.developing),
    (0.60, ProgrammingCapability.competent),
    (0.80, ProgrammingCapability.proficient),
    (1.01, ProgrammingCapability.expert),
]
HINT_ORDER = [HintLevel.conceptual, HintLevel.directional, HintLevel.structural,
              HintLevel.targeted, HintLevel.near_solution]
_DEFAULT_HINT: dict[ProgrammingCapability, HintLevel] = {
    ProgrammingCapability.novice: HintLevel.conceptual,
    ProgrammingCapability.developing: HintLevel.directional,
    ProgrammingCapability.competent: HintLevel.structural,
    ProgrammingCapability.proficient: HintLevel.targeted,
    ProgrammingCapability.expert: HintLevel.near_solution,
}
_TOPIC_PATTERNS: list[tuple[re.Pattern[str], ProgrammingTopic]] = [
    (re.compile(r"\b(sort|search|traverse|graph|tree|path|bfs|dfs|dijkstra|algorithm)\b", re.I), ProgrammingTopic.algorithms),
    (re.compile(r"\b(array|list|dict|map|set|stack|queue|linked list|hash|tuple)\b", re.I), ProgrammingTopic.data_structures),
    (re.compile(r"\b(error|bug|traceback|exception|crash|fix|not working|wrong output)\b", re.I), ProgrammingTopic.debugging),
    (re.compile(r"\b(class|interface|pattern|architecture|design|solid|oop|abstraction)\b", re.I), ProgrammingTopic.design),
    (re.compile(r"\b(import|library|package|module|pip|npm|framework|api|sdk)\b", re.I), ProgrammingTopic.libraries),
    (re.compile(r"\b(syntax|indent|colon|bracket|parenthes|keyword|variable|function|def |print\()\b", re.I), ProgrammingTopic.syntax),
]


def _score_to_capability(score: float) -> ProgrammingCapability:
    for threshold, cap in _SCORE_TO_CAP:
        if score < threshold:
            return cap
    return ProgrammingCapability.expert


def infer_topic(text: str) -> ProgrammingTopic:
    for pattern, topic in _TOPIC_PATTERNS:
        if pattern.search(text):
            return topic
    return ProgrammingTopic.general


def default_hint_level(cap: ProgrammingCapability) -> HintLevel:
    return _DEFAULT_HINT[cap]


def escalate_hint(current: HintLevel) -> HintLevel:
    idx = HINT_ORDER.index(current)
    return HINT_ORDER[min(idx + 1, len(HINT_ORDER) - 1)]


class CapabilityAnalyzer:
    """Analyzes learner messages to build and maintain a CapabilityProfile."""
    MAX_SIGNALS = 100
    ALPHA = 0.3

    def analyze_turn(
        self,
        profile: CapabilityProfile,
        *,
        user_message: str,
        user_responded_correctly: bool | None = None,
        needed_hint_escalation: bool = False,
        self_corrected: bool = False,
    ) -> CapabilityProfile:
        profile.total_questions += 1
        signals: list[CapabilitySignal] = []
        if _CORRECT_VOCAB.search(user_message):
            signals.append(CapabilitySignal(signal_type="correct_vocab", value="matched", weight=0.6))
        if _CONFUSION.search(user_message):
            signals.append(CapabilitySignal(signal_type="confusion", value="expressed", weight=-0.5))
        if _SYNTAX_Q.search(user_message):
            signals.append(CapabilitySignal(signal_type="syntax_only", value="matched", weight=-0.3))
        if _SELF_CORRECT.search(user_message):
            signals.append(CapabilitySignal(signal_type="self_correction", value="detected", weight=0.5))
            profile.self_corrections += 1
        if _DESIGN.search(user_message):
            signals.append(CapabilitySignal(signal_type="design_thinking", value="detected", weight=0.7))
        if _DEBUG_CONTEXT.search(user_message):
            signals.append(CapabilitySignal(signal_type="debug_context", value="detected", weight=0.4))
        if user_responded_correctly is True:
            signals.append(CapabilitySignal(signal_type="correct_reasoning", value="yes", weight=0.6))
            profile.correct_attempts += 1
        elif user_responded_correctly is False:
            signals.append(CapabilitySignal(signal_type="wrong_reasoning", value="yes", weight=-0.4))
            profile.struggle_attempts += 1
        if needed_hint_escalation:
            signals.append(CapabilitySignal(signal_type="needed_escalation", value="yes", weight=-0.3))
            profile.hint_progressions += 1
        if self_corrected:
            signals.append(CapabilitySignal(signal_type="self_corrected", value="yes", weight=0.5))
            profile.self_corrections += 1
        if len(user_message.split()) > 60:
            signals.append(CapabilitySignal(signal_type="articulate_q", value="long", weight=0.2))
        profile.signals.extend(signals)
        profile.signals = profile.signals[-self.MAX_SIGNALS:]
        profile = self._recompute(profile)
        topic = infer_topic(user_message).value
        if topic not in profile.recent_topics:
            profile.recent_topics.append(topic)
        profile.recent_topics = profile.recent_topics[-10:]
        return profile

    def get_hint_level(
        self,
        profile: CapabilityProfile,
        *,
        topic: ProgrammingTopic = ProgrammingTopic.general,
        is_followup: bool = False,
        previous_hint_level: HintLevel | None = None,
    ) -> HintLevel:
        cap = profile.topic_capability.get(topic.value, profile.capability)
        base = default_hint_level(cap)
        if is_followup and previous_hint_level is not None:
            return escalate_hint(previous_hint_level)
        return base

    def _recompute(self, profile: CapabilityProfile) -> CapabilityProfile:
        signals = profile.signals[-30:]
        if not signals:
            return profile
        total_w = weighted_sum = 0.0
        for i, sig in enumerate(signals):
            rw = (i + 1) / len(signals)
            w = sig.weight * rw
            weighted_sum += w
            total_w += abs(w)
        if total_w == 0:
            return profile
        normalized = max(0.0, min(1.0, (weighted_sum / total_w + 1.0) / 2.0))
        current = _CAP_SCORE[profile.capability]
        blended = self.ALPHA * normalized + (1 - self.ALPHA) * current
        profile.capability = _score_to_capability(blended)
        profile.confidence = min(1.0, len(profile.signals) / 20.0)
        return profile

    def summary_text(self, profile: CapabilityProfile) -> str:
        lines = [
            f"Capability: **{profile.capability.value}** (confidence: {profile.confidence:.0%})",
            f"Questions: {profile.total_questions}  |  Correct: {profile.correct_attempts}  |  "
            f"Struggled: {profile.struggle_attempts}  |  Self-corrected: {profile.self_corrections}",
        ]
        if profile.recent_topics:
            lines.append(f"Topics: {', '.join(profile.recent_topics)}")
        return "\n".join(lines)
