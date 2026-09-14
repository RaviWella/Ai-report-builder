"""Chat intent gate tests (pure, no DB) — greetings/help/off-topic vs report."""

from __future__ import annotations

import pytest

from app.services.chat_intent import classify_message, reply_for


@pytest.mark.parametrize("msg", [
    "Hi", "hello", "Hey!", "Good morning", "good evening", "hiya", "yo",
    "thanks", "Thank you", "thx", "bye", "see you", "ok", "cool",
    "how are you", "sup", "", "   ", "hi there", "hello!!!",
])
def test_smalltalk_is_classified(msg):
    assert classify_message(msg) == "smalltalk"


@pytest.mark.parametrize("msg", [
    "who are you", "what can you do", "what is this", "help me",
    "how does this work", "what kind of reports can you build",
])
def test_help_is_classified(msg):
    assert classify_message(msg) == "help"


@pytest.mark.parametrize("msg", [
    "employee details name department",
    "headcount by department",
    "total net pay this month",
    "show me employees who joined last year",
    "average salary by designation",
    "list all active staff with their basic salary",  # leads with 'list', not a greeting
])
def test_report_requests_pass_through(msg):
    assert classify_message(msg) == "report"


def test_replies_are_non_empty_and_distinct_role():
    assert reply_for("help").strip()
    assert reply_for("smalltalk").startswith("Hi")
    # both steer the user toward report examples
    assert "headcount by department" in reply_for("help")
    assert "headcount by department" in reply_for("smalltalk")
