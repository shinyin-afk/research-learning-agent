"""
Hint-focused programming assistant UI.
Run: uv run streamlit run app/mentor_ui.py
"""
from __future__ import annotations

import uuid
import traceback

import streamlit as st

from research_learning_agent.mentor import ProgrammingMentor
from research_learning_agent.programming_schemas import (
    HintLevel, ProgrammingCapability,
)
from research_learning_agent.capability_analyzer import escalate_hint, HINT_ORDER
from research_learning_agent.logging_utils import get_logger

from dotenv import load_dotenv

load_dotenv()

logger = get_logger("MentorUI")

MENTOR_KEY = "mentor"


def _init_state() -> None:
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []  # list[dict(role, content)]
    if "hint_levels" not in st.session_state:
        st.session_state.hint_levels = []  # per assistant turn


@st.cache_resource
def _get_mentor() -> ProgrammingMentor:
    return ProgrammingMentor()


def _render_capability(profile) -> None:
    cap = profile.capability.value
    conf = profile.confidence
    st.sidebar.metric("Inferred capability", cap)
    st.sidebar.progress(conf, text=f"confidence {conf:.0%}")
    st.sidebar.caption(
        f"{profile.total_questions} questions · "
        f"{profile.correct_attempts} correct · "
        f"{profile.struggle_attempts} struggled"
    )
    if profile.recent_topics:
        st.sidebar.caption("Topics: " + ", ".join(profile.recent_topics))


def main() -> None:
    st.set_page_config(page_title="Programming Mentor", page_icon="🧭")
    _init_state()
    mentor = _get_mentor()

    st.title("🧭 Programming Mentor")
    st.caption("I give hints, not answers. You do the thinking — I guide you there.")

    # Sidebar
    st.sidebar.header("Learner Profile")
    profile = mentor.get_profile(st.session_state.user_id)
    _render_capability(profile)

    if st.sidebar.button("Reset this conversation"):
        mentor.reset_session(st.session_state.user_id)
        st.session_state.messages = []
        st.session_state.hint_levels = []
        st.rerun()

    # Optional input for code/error (advanced panel)
    with st.sidebar.expander("Paste code / error (optional)", expanded=False):
        code_snippet = st.text_area("Your code", height=80, key="code_snip")
        error_message = st.text_area("Error message", height=60, key="err_msg")

    # Chat history
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and i // 2 < len(st.session_state.hint_levels):
                level = st.session_state.hint_levels[i // 2]
                st.caption(f"hint level: {level}")

    # Input
    prompt = st.chat_input("Describe your programming problem or question...")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking of a hint..."):
                hint, profile = mentor.answer(
                    user_id=st.session_state.user_id,
                    message=prompt,
                    code_snippet=code_snippet or None,
                    error_message=error_message or None,
                )
        except Exception as e:
            logger.error("Mentor error: %s\n%s", e, traceback.format_exc())
            st.error(f"Something went wrong: {e}")
            return

        st.markdown(hint.hint)
        if hint.socratic_question:
            st.markdown(f"**💭 {hint.socratic_question}**")
        if hint.analogy:
            st.info(f"🔍 Analogy: {hint.analogy}")
        if hint.concept_to_review:
            st.caption(f"📚 Concept to review: {hint.concept_to_review}")
        if hint.encouragement:
            st.caption(f"✨ {hint.encouragement}")
        st.caption(f"hint level: {hint.hint_level.value}")

        # Deeper hint button
        if st.button("Give me a deeper hint", key=f"deeper_{len(st.session_state.messages)}"):
            next_level = escalate_hint(hint.hint_level)
            if next_level == hint.hint_level:
                st.info("You've reached the deepest level — try writing out your reasoning first!")
            else:
                # Re-answer as a followup to escalate
                deeper, profile2 = mentor.answer(
                    user_id=st.session_state.user_id,
                    message="I still need a hint — can you give me a deeper one?",
                    is_followup=True,
                )
                st.markdown("---")
                st.markdown(deeper.hint)
                if deeper.socratic_question:
                    st.markdown(f"**💭 {deeper.socratic_question}**")
                st.caption(f"hint level: {deeper.hint_level.value}")
                hint = deeper

    st.session_state.messages.append({"role": "assistant", "content": hint.hint})
    st.session_state.hint_levels.append(hint.hint_level.value)

    # Refresh sidebar capability display
    _render_capability(profile)


if __name__ == "__main__":
    main()
