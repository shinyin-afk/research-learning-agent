# Hint-Focused Programming Assistant

A Socratic, hint-based programming mentor that **never gives direct answers**.
It gauges each learner's programming capability from their conversation history
and calibrates the depth of hints accordingly.

## Core Principle

The agent's job is **not to solve problems for the learner** — it guides them to
discover the solution themselves. Every response is a *hint*, not an *answer*.

## Key Components

| Module | Responsibility |
| --- | --- |
| `programming_schemas.py` | Data models: `HintLevel`, `ProgrammingCapability`, `CapabilityProfile`, `HintResponse`, etc. |
| `capability_analyzer.py` | Deterministic gauging of learner capability from message text + behavior. No LLM calls. |
| `hint_generator.py` | LLM-powered Socratic hint generation, calibrated by capability + hint level. |
| `mentor.py` | `ProgrammingMentor` — orchestrates gauging → calibration → hint → memory. |
| `stores/capability_store.py` | Persistent per-learner memory (capability profile + past signals). |
| `app/mentor_ui.py` | Streamlit UI. |

## Hint Ladder

Hints escalate from gentle to near-solution (but never a full solution):

```
conceptual → directional → structural → targeted → near_solution
```

The starting hint level is derived from the learner's inferred capability:

| Capability | Starting hint |
| --- | --- |
| novice | conceptual |
| developing | directional |
| competent | structural |
| proficient | targeted |
| expert | near_solution |

When a learner asks for another hint *without progress* (a follow-up), the agent
escalates one level. When they show correct reasoning, the capability gauge rises
and future hints start deeper.

## Capability Gauging (Memory-Driven)

The analyzer builds a rolling `CapabilityProfile` per learner from signals:

- **Positive** — correct vocabulary (e.g. "time complexity", "memoization"),
  self-corrections, design-thinking questions, debugging with context,
  confirmed-correct reasoning.
- **Negative** — expressed confusion, syntax-only questions, needing repeated
  escalation, incorrect reasoning.

These signals are weighted (recency-weighted EMA) into a capability tier, with a
confidence score that grows as more evidence accumulates. The profile persists to
`data/capability_profiles.json`, giving the agent **long-term memory** of each
learner's past prompts and progress.

## Running

```bash
# Web UI
uv run streamlit run app/mentor_ui.py

# Or (once deps are available) programmatically:
from research_learning_agent.mentor import ProgrammingMentor
mentor = ProgrammingMentor()
hint, profile = mentor.answer(user_id="alice", message="How do I reverse a linked list?")
print(hint.hint)          # a hint, not the answer
print(profile.capability) # inferred capability tier
```

## Testing

```bash
uv run pytest tests/unit/test_capability_analyzer.py tests/unit/test_mentor.py
```

The capability analyzer and mentor escalation logic are fully deterministic and
unit-tested without needing an API key.
