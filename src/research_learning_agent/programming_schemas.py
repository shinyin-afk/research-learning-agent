"""
Schemas for the hint-focused programming assistant.
These extend the base schemas without replacing them.
"""
from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class HintLevel(str, Enum):
    """Granular hint levels — ordered from most gentle to most explicit."""
    conceptual    = "conceptual"     # What concept applies here? (no code)
    directional   = "directional"    # Which direction / approach to think about
    structural    = "structural"     # Skeleton / pseudo-code scaffold
    targeted      = "targeted"       # Specific part of the logic explained
    near_solution = "near_solution"  # Almost the answer — still no full code


class ProgrammingCapability(str, Enum):
    """Inferred capability tier of the learner."""
    novice       = "novice"        # < 3 coherent attempts; struggles with syntax/concepts
    developing   = "developing"    # Some grasp; making logical errors
    competent    = "competent"     # Solid fundamentals; needs nudges on patterns
    proficient   = "proficient"    # Strong; occasional blind spots
    expert       = "expert"        # Near-mastery; wants confirmation or edge cases


class ProgrammingTopic(str, Enum):
    """Broad topic bucket inferred from the question."""
    syntax        = "syntax"
    data_structures = "data_structures"
    algorithms    = "algorithms"
    debugging     = "debugging"
    design        = "design"
    libraries     = "libraries"
    general       = "general"


class CapabilitySignal(BaseModel):
    """A single piece of evidence used to gauge learner capability."""
    signal_type: str   # e.g. "correct_term_usage", "wrong_approach", "follow_up_depth"
    value: str
    weight: float = 1.0  # positive = capability, negative = struggle


class CapabilityProfile(BaseModel):
    """Running assessment of a learner's programming capability."""
    user_id: str = "default"
    capability: ProgrammingCapability = ProgrammingCapability.developing
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # Rolling evidence
    signals: list[CapabilitySignal] = Field(default_factory=list)

    # Per-topic overrides (some learners are strong in one area, weak in another)
    topic_capability: dict[str, ProgrammingCapability] = Field(default_factory=dict)

    # Aggregate interaction stats
    total_questions:    int = 0
    correct_attempts:   int = 0   # user showed correct reasoning
    struggle_attempts:  int = 0   # user showed confusion / wrong direction
    hint_progressions:  int = 0   # times user needed a deeper hint
    self_corrections:   int = 0   # times user corrected themselves after a hint

    # Recent topic coverage
    recent_topics: list[str] = Field(default_factory=list)


class HintRequest(BaseModel):
    """Input to the hint generator."""
    user_id: str
    question: str                # The learner's current question or problem description
    code_snippet: str | None = None   # Optional: code they've already written
    error_message: str | None = None  # Optional: compiler/runtime error
    topic: ProgrammingTopic = ProgrammingTopic.general
    capability: ProgrammingCapability = ProgrammingCapability.developing
    hint_level: HintLevel = HintLevel.conceptual
    session_context: list[dict[str, Any]] = Field(default_factory=list)  # recent turns


class HintResponse(BaseModel):
    """Output from the hint generator."""
    hint_level: HintLevel
    capability_used: ProgrammingCapability
    topic: ProgrammingTopic

    # The actual hint text — never a full solution
    hint: str

    # Socratic question to push the learner to think further
    socratic_question: str | None = None

    # Optional: concept the learner should review
    concept_to_review: str | None = None

    # Optional: analogies or mental models offered
    analogy: str | None = None

    # Whether the agent thinks the learner is ready for the next hint level
    suggest_next_hint: bool = False

    # Encouragement / metacognitive nudge
    encouragement: str | None = None
