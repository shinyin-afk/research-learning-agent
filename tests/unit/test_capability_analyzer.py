"""Tests for the capability analyzer (deterministic, no LLM)."""
from research_learning_agent.capability_analyzer import (
    CapabilityAnalyzer, infer_topic, escalate_hint, default_hint_level,
)
from research_learning_agent.programming_schemas import (
    CapabilityProfile, ProgrammingCapability, ProgrammingTopic, HintLevel,
)


def _fresh_profile() -> CapabilityProfile:
    return CapabilityProfile(user_id="test_user")


def test_infer_topic_algorithms():
    assert infer_topic("how do I do binary search on this sorted list") == ProgrammingTopic.algorithms


def test_infer_topic_debugging():
    assert infer_topic("my code throws a traceback, why is it not working") == ProgrammingTopic.debugging


def test_infer_topic_default():
    assert infer_topic("hello there") == ProgrammingTopic.general


def test_escalate_hint_moves_up():
    assert escalate_hint(HintLevel.conceptual) == HintLevel.directional
    assert escalate_hint(HintLevel.near_solution) == HintLevel.near_solution  # clamped


def test_default_hint_level_mapping():
    assert default_hint_level(ProgrammingCapability.novice) == HintLevel.conceptual
    assert default_hint_level(ProgrammingCapability.expert) == HintLevel.near_solution


def test_confusion_lowers_capability():
    a = CapabilityAnalyzer()
    p = _fresh_profile()
    p = a.analyze_turn(p, user_message="I'm completely lost, I don't understand recursion at all")
    assert p.total_questions == 1
    # Confusion is a negative signal; capability should not exceed developing
    assert p.capability in {ProgrammingCapability.novice, ProgrammingCapability.developing}


def test_correct_vocab_raises_capability():
    a = CapabilityAnalyzer()
    p = _fresh_profile()
    for _ in range(5):
        p = a.analyze_turn(
            p,
            user_message="I'm considering the time complexity of this dynamic programming approach and its edge cases",
            user_responded_correctly=True,
        )
    assert p.correct_attempts == 5
    assert p.capability in {ProgrammingCapability.competent, ProgrammingCapability.proficient, ProgrammingCapability.expert}


def test_escalation_on_followup():
    a = CapabilityAnalyzer()
    p = _fresh_profile()
    # default capability is developing → maps to directional
    base = a.get_hint_level(p, topic=ProgrammingTopic.algorithms)
    assert base == HintLevel.directional

    # followup escalates
    escalated = a.get_hint_level(
        p, topic=ProgrammingTopic.algorithms,
        is_followup=True, previous_hint_level=base,
    )
    assert escalated == HintLevel.structural


def test_confidence_grows_with_signals():
    a = CapabilityAnalyzer()
    p = _fresh_profile()
    assert p.confidence == 0.5
    for _ in range(20):
        p = a.analyze_turn(p, user_message="binary search time complexity")
    assert p.confidence >= 0.9


def test_self_correction_tracked():
    a = CapabilityAnalyzer()
    p = _fresh_profile()
    p = a.analyze_turn(p, user_message="oh wait, actually I see — it's because of the off-by-one", self_corrected=True)
    assert p.self_corrections >= 1
