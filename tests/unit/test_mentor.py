"""Tests for the capability store + mentor escalation logic (no LLM)."""
from pathlib import Path

from research_learning_agent.programming_schemas import (
    CapabilityProfile, ProgrammingCapability,
)
from research_learning_agent.stores.capability_store import CapabilityStore
from research_learning_agent.mentor import ProgrammingMentor
from research_learning_agent.programming_schemas import HintLevel


def test_capability_store_roundtrip(tmp_path: Path):
    store = CapabilityStore(path=tmp_path / "caps.json")
    profile = CapabilityProfile(user_id="alice", capability=ProgrammingCapability.competent)
    store.save(profile)
    loaded = store.load("alice")
    assert loaded is not None
    assert loaded.capability == ProgrammingCapability.competent
    assert loaded.user_id == "alice"


def test_capability_store_missing_user(tmp_path: Path):
    store = CapabilityStore(path=tmp_path / "caps.json")
    store.save(CapabilityProfile(user_id="alice"))
    assert store.load("bob") is None


def test_mentor_get_profile_defaults(tmp_path: Path, monkeypatch):
    store = CapabilityStore(path=tmp_path / "caps.json")
    mentor = ProgrammingMentor()
    mentor.store = store
    profile = mentor.get_profile("new_user")
    assert profile.user_id == "new_user"
    assert profile.capability == ProgrammingCapability.developing


def test_mentor_escalation_prompt():
    mentor = ProgrammingMentor()
    # no prior hint → None
    assert mentor.escalation_prompt("alice") is None
    # set a prior hint level
    mentor._last_hint_level["alice"] = HintLevel.conceptual
    prompt = mentor.escalation_prompt("alice")
    assert prompt is not None
    assert "directional" in prompt  # escalated from conceptual


def test_mentor_reset_session_keeps_persistent(tmp_path: Path):
    store = CapabilityStore(path=tmp_path / "caps.json")
    mentor = ProgrammingMentor()
    mentor.store = store
    mentor._last_hint_level["alice"] = HintLevel.structural
    mentor._session_context["alice"] = [{"role": "user", "content": "hi"}]
    mentor.reset_session("alice")
    assert "alice" not in mentor._session_context
    assert "alice" not in mentor._last_hint_level
