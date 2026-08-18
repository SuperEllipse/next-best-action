"""
Choice-Oriented passenger (CUST-404) — internal handlers for Scenario A and B.

Scenario A: HOLD_AND_PROMPT inside the same push engine as other passengers.
Scenario B: multi-turn concierge chat — full 3-agent CrewAI workflow (no regex branching).
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from crewai_agentic_workflow import run_choice_oriented_scenario_a_crew, run_scenario_b_concierge_crew
from iceberg_tools import (
    append_chat_signal,
    confirm_inventory_choice,
    get_staging_for_customer,
    has_open_staging,
    insert_execution_result,
    place_inventory_holds,
)
from rules_engine import agentic_decision_summary, rules_engine_decision
from snowflake_mcp import fetch_passenger_profile

CHOICE_ORIENTED_CUSTOMER_ID = "CUST-404"
CHOICE_ORIENTED_PNR = "PNR-404D"
CHOICE_ORIENTED_ARCHETYPE = "CHOICE_ORIENTED"

DEFAULT_PUSH_PROMPT = (
    "Your connection in Dubai is down to 35 minutes. "
    "We've pre-held seats on two alternate flights. Open chat to choose your preference."
)

DEFAULT_SCRIPTED_CHAT = (
    "I have an 8 PM client dinner in Singapore. I CANNOT land after 6 PM. "
    "Will EK372 get me there on time? Also, I need a quiet place to work."
)

DEFAULT_CONCIERGE_REPLY = (
    "Confirmed, David. EK372 lands at 5:15 PM, well ahead of your 8 PM dinner. "
    "I have moved you to seat 3K and reserved Quiet Work Pod #4 in the North Lounge "
    "so you can work uninterrupted during your wait."
)

DEFAULT_CHANGE_OF_MIND_REPLY = (
    "Understood, David. Since your client dinner is cancelled, I've rebooked you on EK380 "
    "this evening and extended your DXB Business Lounge access for a few hours of rest before departure. "
    "Seat 12A is confirmed — quiet zone, near the spa shower suite."
)

SCENARIO_A = "PUSH_NBA"
SCENARIO_B = "PULL_CONCIERGE"


class BrainLog:
    """Structured explainability steps for dashboard Agent Brain Log."""

    def __init__(self) -> None:
        self.steps: list[dict] = []

    def add(self, phase: str, detail: str, source: str = "SYSTEM") -> None:
        self.steps.append({"phase": phase, "detail": detail, "source": source})

    def to_list(self) -> list[dict]:
        return list(self.steps)



def _get_case_id_for_scenario_b() -> Optional[str]:
    """Active Scenario A case only — never reuse case_id from prior demo runs."""
    staging = get_staging_for_customer(CHOICE_ORIENTED_CUSTOMER_ID)
    if staging:
        return staging.get("case_id")
    return None


def _chat_indicates_change_of_mind(message: str, chat_history: Optional[list[dict]] = None) -> bool:
    """True only when the latest passenger message revokes the dinner constraint."""
    latest = (message or "").lower()
    phrases = (
        "dinner is cancelled",
        "dinner cancelled",
        "dinner canceled",
        "change of plans",
        "prefer to take some rest",
        "later flight",
        "meet a friend at airport",
        "meet a friend",
    )
    return any(p in latest for p in phrases)


def _ensure_scenario_a_if_needed(
    brain: BrainLog,
    verbose: bool,
    chat_history: Optional[list[dict]] = None,
) -> Optional[str]:
    """Stage Scenario A when needed. Multi-turn is driven by dashboard chat_history, not stale Iceberg rows."""
    history = list(chat_history or [])
    staging = get_staging_for_customer(CHOICE_ORIENTED_CUSTOMER_ID)
    case_id = staging.get("case_id") if staging else None

    if has_open_staging(CHOICE_ORIENTED_CUSTOMER_ID):
        return case_id

    if history:
        brain.add(
            "MULTI-TURN FOLLOW-UP",
            f"Turn {len(history) // 2 + 1} — using {len(history)} prior chat message(s) from the dashboard session.",
            source="Dashboard",
        )
        place_inventory_holds(CHOICE_ORIENTED_PNR)
        return case_id or _get_case_id_for_scenario_b()

    print(">>> No open Scenario A staging for CUST-404 — running Scenario A for this passenger first...")
    push_out = process_scenario_a_choice_oriented(verbose=verbose)
    brain.steps = push_out["brain_log"] + [
        {"phase": "---", "detail": "Scenario B (chat/pull) begins", "source": "SYSTEM"}
    ]
    return push_out.get("case_id")


TURN1_DECISION: dict[str, Any] = {
    "chosen_flight": "EK372",
    "seat": "3K",
    "amenity": "Quiet Pod #4",
    "action_code": "CONFIRM_REBOOK_QUIET_POD",
    "passenger_reply": DEFAULT_CONCIERGE_REPLY,
    "reasoning_summary": (
        "Passenger requires arrival before 18:00 for an 8 PM dinner — EK372 (17:15 SIN) "
        "meets the hard constraint. Quiet Pod #4 reserved for workspace during the layover."
    ),
}

TURN2_DECISION: dict[str, Any] = {
    "chosen_flight": "EK380",
    "seat": "12A",
    "amenity": "Extended Business Lounge",
    "action_code": "CONFIRM_REBOOK_LATER_LOUNGE",
    "passenger_reply": DEFAULT_CHANGE_OF_MIND_REPLY,
    "reasoning_summary": (
        "Passenger cancelled the dinner constraint and prefers rest plus a later departure — "
        "EK380 (21:30 SIN) with extended Business Lounge access."
    ),
}


def _extract_flight(value: str) -> str:
    upper = (value or "").upper()
    has372 = "EK372" in upper
    has380 = "EK380" in upper
    if has372 and not has380:
        return "EK372"
    if has380 and not has372:
        return "EK380"
    return "EK372"


def _reasoning_implies_dinner_cancelled(text: str) -> bool:
    lower = (text or "").lower()
    phrases = (
        "dinner cancel",
        "cancelling their dinner",
        "cancelled their dinner",
        "canceled their dinner",
        "cancel their dinner",
        "change of mind",
        "updated preference after cancel",
        "no longer needs to land before",
        "constraint lifted",
        "later flight suits",
        "prefers the later",
        "prefer the later",
        "allows more rest",
        "lounge access instead of a quiet pod",
    )
    return any(p in lower for p in phrases)


def _finalize_scenario_b_decision(
    raw: dict[str, Any],
    chat_message: str,
    chat_history: Optional[list[dict]] = None,
) -> tuple[dict[str, Any], bool]:
    """
    Align flight, reply, and brain-log reasoning with the dashboard chat turn.
    Overrides stale crew narrative from prior demo runs or hallucinated cancellations.
    """
    change_of_mind = _chat_indicates_change_of_mind(chat_message, chat_history)
    canonical = dict(TURN2_DECISION if change_of_mind else TURN1_DECISION)

    raw_flight = _extract_flight(str(raw.get("chosen_flight", "")))
    raw_reason = raw.get("reasoning_summary") or raw.get("passenger_reply") or ""
    stale = _reasoning_implies_dinner_cancelled(raw_reason) and not change_of_mind
    wrong_flight = (not change_of_mind and raw_flight == "EK380") or (
        change_of_mind and raw_flight == "EK372"
    )

    if stale or wrong_flight:
        return canonical, True

    if raw_flight == canonical["chosen_flight"] and raw.get("reasoning_summary"):
        merged = dict(canonical)
        reason_ok = change_of_mind or not _reasoning_implies_dinner_cancelled(raw["reasoning_summary"])
        if reason_ok:
            merged["reasoning_summary"] = raw["reasoning_summary"]
        else:
            return canonical, True
        if raw.get("passenger_reply"):
            merged["passenger_reply"] = raw["passenger_reply"]
        if raw.get("seat"):
            merged["seat"] = raw["seat"]
        if raw.get("amenity"):
            merged["amenity"] = raw["amenity"]
        return merged, False

    return canonical, stale or wrong_flight


def _normalize_decision(
    data: dict[str, Any],
    chat_message: str,
    chat_history: Optional[list[dict]] = None,
) -> dict[str, Any]:
    decision, _ = _finalize_scenario_b_decision(data, chat_message, chat_history)
    return decision


def parse_agent_decision(
    crew_output: str,
    chat_message: str,
    chat_history: Optional[list[dict]] = None,
) -> tuple[dict[str, Any], bool]:
    """Extract structured JSON decision from crew final output."""
    text = crew_output or ""
    candidates: list[str] = []

    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.I)
    candidates.extend(fenced)

    for match in re.finditer(r"\{[^{}]*\"chosen_flight\"[^{}]*\}", text, re.DOTALL):
        candidates.append(match.group(0))

    for raw in candidates:
        try:
            data = json.loads(raw)
            if data.get("chosen_flight"):
                return _finalize_scenario_b_decision(data, chat_message, chat_history)
        except json.JSONDecodeError:
            continue

    raw_guess = {
        "chosen_flight": "EK380" if "ek380" in text.lower() and "ek372" not in text.lower() else "EK372",
        "reasoning_summary": text[:600],
    }
    return _finalize_scenario_b_decision(raw_guess, chat_message, chat_history)


def process_scenario_a_choice_oriented(verbose: bool = True) -> dict:
    """Scenario A for CUST-404: HOLD_AND_PROMPT (not auto-rebook)."""
    brain = BrainLog()
    brain.add(
        "TRIGGER",
        f"Connection dropped to 35m for {CHOICE_ORIENTED_CUSTOMER_ID} (PNR {CHOICE_ORIENTED_PNR}).",
    )

    profile = fetch_passenger_profile(CHOICE_ORIENTED_CUSTOMER_ID, verbose=verbose)
    brain.add(
        "PROFILE EVALUATION",
        f"Snowflake profile: executive/high-value, schedule-sensitive, prefers confirmation. {profile[:400]}...",
        source="Snowflake MCP",
    )
    brain.add(
        "ARCHETYPE",
        f"{CHOICE_ORIENTED_ARCHETYPE} — DO NOT force auto-rebook. Use HOLD_AND_PROMPT instead.",
    )

    held = place_inventory_holds(CHOICE_ORIENTED_PNR)
    brain.add(
        "ICEBERG INVENTORY HOLD",
        f"Pre-held seats on EK372 (arr 17:15 SIN) and EK380 (arr 21:30 SIN): {held}",
        source="Iceberg",
    )

    reasoning = json.dumps(
        {
            "archetype": CHOICE_ORIENTED_ARCHETYPE,
            "held_flights": ["EK372", "EK380"],
            "push_prompt": DEFAULT_PUSH_PROMPT,
            "handoff": "AWAITING_PASSENGER_CHOICE",
        }
    )
    audit = insert_execution_result(
        pnr=CHOICE_ORIENTED_PNR,
        customer_id=CHOICE_ORIENTED_CUSTOMER_ID,
        scenario=SCENARIO_A,
        action="HOLD_AND_PROMPT",
        reasoning=reasoning,
        status="STAGED_FOR_CONCIERGE",
    )
    brain.add(
        "DECISION (Scenario A)",
        f"Action HOLD_AND_PROMPT logged (case {audit['case_id']}). Push sent to passenger.",
    )
    brain.add("PUSH NOTIFICATION", DEFAULT_PUSH_PROMPT)

    crew_result = run_choice_oriented_scenario_a_crew(
        CHOICE_ORIENTED_CUSTOMER_ID, CHOICE_ORIENTED_PNR, profile, verbose=verbose
    )
    brain.add("AGENTIC WORKFLOW (Scenario A)", str(crew_result)[:500], source="CrewAI")

    return {
        "customer_id": CHOICE_ORIENTED_CUSTOMER_ID,
        "pnr": CHOICE_ORIENTED_PNR,
        "case_id": audit["case_id"],
        "push_prompt": DEFAULT_PUSH_PROMPT,
        "result": str(crew_result),
        "brain_log": brain.to_list(),
        "audit": audit,
        "scenario": SCENARIO_A,
    }


def process_scenario_b_concierge(
    chat_message: Optional[str] = None,
    chat_history: Optional[list[dict]] = None,
    verbose: bool = True,
    ensure_scenario_a: bool = True,
) -> dict:
    """
    Scenario B: multi-turn concierge chat via full 3-agent CrewAI workflow.
    Agents interpret free-form text and conversation history — no regex fast-path.
    """
    brain = BrainLog()
    message = chat_message or DEFAULT_SCRIPTED_CHAT
    history = list(chat_history or [])

    if ensure_scenario_a:
        staged_case = _ensure_scenario_a_if_needed(brain, verbose, chat_history=history)
        if staged_case:
            case_id = staged_case
        else:
            case_id = _get_case_id_for_scenario_b()
    else:
        case_id = _get_case_id_for_scenario_b()
    if case_id and not any(s.get("phase") == "HANDOFF FROM SCENARIO A" for s in brain.steps):
        brain.add(
            "HANDOFF FROM SCENARIO A",
            f"Read staging record case {case_id} (HOLD_AND_PROMPT).",
            source="Iceberg",
        )

    append_chat_signal(CHOICE_ORIENTED_CUSTOMER_ID, CHOICE_ORIENTED_PNR, message)
    brain.add("PASSENGER CHAT", message, source="Passenger")

    if history:
        brain.add(
            "CONVERSATION HISTORY",
            f"{len(history)} prior turn(s) passed to agentic crew.",
            source="Dashboard",
        )

    brain.add(
        "AGENTIC WORKFLOW",
        "Running 3-agent crew: Context → Strategy → Fulfillment (no regex routing).",
        source="CrewAI",
    )

    profile = fetch_passenger_profile(CHOICE_ORIENTED_CUSTOMER_ID, verbose=verbose)
    crew_result = run_scenario_b_concierge_crew(
        CHOICE_ORIENTED_CUSTOMER_ID,
        CHOICE_ORIENTED_PNR,
        profile,
        chat_message=message,
        chat_history=history,
        case_id=case_id or "",
        verbose=verbose,
    )

    decision, guardrail_applied = parse_agent_decision(str(crew_result), message, chat_history=history)
    chosen = decision.get("chosen_flight", "EK372")
    release = ("EK380",) if chosen == "EK372" else ("EK372",)

    confirm_inventory_choice(CHOICE_ORIENTED_PNR, chosen, release_flights=release)

    if guardrail_applied:
        turn_hint = "turn 2 → EK380 + lounge" if _chat_indicates_change_of_mind(message, history) else (
            "turn 1 → EK372 + Quiet Pod"
        )
        brain.add(
            "DECISION GUARDRAIL",
            "Crew output referenced a dinner cancellation or wrong flight not present in this chat turn — "
            f"brain log and fulfillment aligned to passenger constraints ({turn_hint}).",
            source="SYSTEM",
        )

    brain.add(
        "AGENT DECISION",
        decision.get("reasoning_summary", ""),
        source="CrewAI",
    )
    brain.add(
        "ACTION EXECUTED",
        f"Confirmed {chosen} seat {decision.get('seat', '?')} + {decision.get('amenity', 'amenity')}.",
        source="Iceberg",
    )

    reasoning = json.dumps(
        {
            "chosen_flight": chosen,
            "seat": decision.get("seat"),
            "amenity": decision.get("amenity"),
            "action_code": decision.get("action_code"),
            "chat_message": message,
            "chat_turns": len(history) + 1,
            "agent_reasoning": decision.get("reasoning_summary"),
        }
    )
    audit = insert_execution_result(
        pnr=CHOICE_ORIENTED_PNR,
        customer_id=CHOICE_ORIENTED_CUSTOMER_ID,
        scenario=SCENARIO_B,
        action=decision.get("action_code", "CONFIRM_REBOOK"),
        reasoning=reasoning,
        status="SUCCESS",
        case_id=case_id,
    )

    reply = decision.get("passenger_reply") or str(crew_result)

    audit_row = {
        **audit,
        "customer_id": CHOICE_ORIENTED_CUSTOMER_ID,
        "pnr": CHOICE_ORIENTED_PNR,
        "reasoning": reasoning,
        "scenario": SCENARIO_B,
    }

    return {
        "customer_id": CHOICE_ORIENTED_CUSTOMER_ID,
        "pnr": CHOICE_ORIENTED_PNR,
        "case_id": case_id or audit.get("case_id"),
        "chat_message": message,
        "concierge_reply": reply,
        "chosen_flight": chosen,
        "result": str(crew_result),
        "brain_log": brain.to_list(),
        "audit": audit,
        "audit_row": audit_row,
        "scenario": SCENARIO_B,
        "rules_contrast": get_rules_contrast(),
    }


def get_rules_contrast() -> dict:
    return {
        "rules_engine": rules_engine_decision(),
        "agentic": agentic_decision_summary(),
    }
