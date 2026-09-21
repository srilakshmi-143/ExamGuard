"""Integrity-report summarizer with an optional LangChain provider and safe fallback."""

import os
from typing import Any, Dict


def generate_integrity_report(data: Dict[str, Any]) -> str:
    score = data.get("integrity_score", data.get("integrity", {}).get("score", 100))
    risk = data.get("risk_label", data.get("integrity", {}).get("risk_level", "Low"))
    events = data.get("events", [])
    counts = {}
    for event in events:
        event_type = str(event.get("event_type", "EVENT")).replace("_", " ").lower()
        counts[event_type] = counts.get(event_type, 0) + 1
    event_summary = ", ".join(f"{count} {name}" for name, count in sorted(counts.items())) or "no flagged events"
    fallback = (
        f"[AI unavailable: set EXAMGUARD_LLM_API_KEY to enable LangChain/OpenAI reporting]\n\n"
        f"Factual session summary\n\n"
        f"The session recorded an integrity score of {score} ({risk} Risk). "
        f"The system recorded {event_summary}. Flagged events remain available for invigilator review."
    )
    if not os.environ.get("EXAMGUARD_LLM_API_KEY"):
        return fallback
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
        prompt = ChatPromptTemplate.from_template("Summarize only these verified examination facts in two sentences: {facts}")
        chain = prompt | ChatOpenAI(api_key=os.environ["EXAMGUARD_LLM_API_KEY"], model=os.environ.get("EXAMGUARD_LLM_MODEL", "gpt-4o-mini"), temperature=0)
        return chain.invoke({"facts": fallback}).content
    except Exception:
        return (
            "[AI unavailable: the configured LangChain provider could not generate a report]\n\n"
            + fallback.split("\n\n", 1)[1]
        )
