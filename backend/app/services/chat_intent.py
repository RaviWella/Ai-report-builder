"""Chat intent gate for the conversational report builder.

A logged-in user can type anything ("Hi", "Good morning", "thanks", "who are
you?") — not just report requests. This deterministic classifier catches
smalltalk / help / off-topic input up front so the chat answers conversationally
instead of trying (and failing) to compile it into a report.

Deterministic + zero-LLM + zero-config: greetings get an instant, free, ms reply
even with no AI key set. Anything not clearly smalltalk is treated as a report
request (the default), so a real query is never swallowed.
"""

from __future__ import annotations

import re

# Whole-message smalltalk (matched against the normalized text).
_GREET = {
    "hi", "hii", "hello", "helo", "hey", "heya", "hiya", "yo", "hai", "greetings",
    "good morning", "good afternoon", "good evening", "good day", "gm",
    "morning", "afternoon", "evening",
}
_THANKS = {"thanks", "thank you", "thank u", "thx", "ty", "cheers", "thankyou", "appreciate it"}
_BYE = {"bye", "goodbye", "good bye", "see you", "see ya", "cya", "later"}
_COURTESY = {
    "how are you", "how r u", "hows it going", "how is it going", "whats up",
    "what is up", "sup", "ok", "okay", "k", "cool", "nice", "great", "fine",
}
# First-word greeting tokens (so "hi there", "hello!" are caught when short).
_GREET_LEAD = {"hi", "hii", "hello", "hey", "heya", "hiya", "yo", "hai", "morning",
               "thanks", "thank", "thankyou", "bye", "cheers", "sup", "greetings", "gm"}
# Phrases that signal the user wants help / to know what this is.
_HELP = (
    "who are you", "what are you", "what can you do", "what do you do",
    "what can i ask", "what should i ask", "how does this work", "how do i use",
    "what is this", "what can this do", "help me", "can you help", "what can you help",
    "how to use", "what kind of reports",
)


def classify_message(message: str) -> str:
    """Return 'smalltalk' | 'help' | 'report'. 'report' is the default so a genuine
    request is never misrouted; only clear smalltalk/help is intercepted."""
    core = re.sub(r"[^a-z0-9 ]", " ", (message or "").lower())
    core = re.sub(r"\s+", " ", core).strip()
    if not core:
        return "smalltalk"
    if any(p in core for p in _HELP):
        return "help"
    if core in _GREET or core in _THANKS or core in _BYE or core in _COURTESY:
        return "smalltalk"
    words = core.split()
    if len(words) <= 3 and words[0] in _GREET_LEAD:
        return "smalltalk"
    return "report"


_GUIDANCE = (
    "I help you build HR reports from your data. Try things like "
    "“employee details — name, department, designation”, “headcount by department”, "
    "or “total net pay this month”. Ask in plain language and we’ll refine it together."
)


def reply_for(kind: str, message: str = "") -> str:
    """The conversational reply for a non-report turn. When a message is given,
    tailor smalltalk (thanks / bye / greeting); otherwise a friendly greeting."""
    if kind == "help":
        return _GUIDANCE
    core = re.sub(r"[^a-z0-9 ]", " ", (message or "").lower())
    core = re.sub(r"\s+", " ", core).strip()
    first = core.split()[0] if core else ""
    if core in _THANKS or first in {"thanks", "thank", "thankyou", "thx", "ty", "cheers"}:
        return "You’re welcome! 🙂 Ask me for another report anytime — e.g. “headcount by department”."
    if core in _BYE or first in {"bye", "goodbye", "cya"}:
        return "Take care! 👋 Come back anytime to build a report — e.g. “headcount by department”."
    if core in {"ok", "okay", "k", "cool", "nice", "great", "fine", "got it", "alright", "sure"}:
        return "👍 Ask for another report whenever you like — e.g. “headcount by department”."
    return "Hi! 👋 " + _GUIDANCE
