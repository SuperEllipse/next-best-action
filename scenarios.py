"""
Scenario A (Push / NBA) and Scenario B (Pull / Concierge).

Scenario A — proactive push for ALL affected passengers (101, 202, 303, 404).
  The uplift engine picks the action per archetype (auto-rebook vs hold-and-invite).
  CUST-404 (Choice-Oriented) gets HOLD_AND_PROMPT inside Scenario A — not a separate flow.

Scenario B — chat/pull conversation for CUST-404 only; executes the choice staged in Scenario A.
"""

from crewai_agentic_workflow import run_irop_workflow
from choice_oriented_passenger import (
    CHOICE_ORIENTED_CUSTOMER_ID,
    DEFAULT_SCRIPTED_CHAT,
    process_scenario_a_choice_oriented,
    process_scenario_b_concierge,
)
from iceberg_tools import get_passengers_for_event

SCENARIO_A = "PUSH_NBA"
SCENARIO_B = "PULL_CONCIERGE"

# All passengers processed by Scenario A (same push engine, different outcomes)
SCENARIO_A_PASSENGERS = ["CUST-101", "CUST-202", "CUST-303", "CUST-404"]


def run_scenario_a(verbose: bool = True) -> dict:
    """Scenario A: proactive push for every passenger — uplift decides the action."""
    passengers = get_passengers_for_event()
    order = {cid: i for i, cid in enumerate(SCENARIO_A_PASSENGERS)}
    targets = sorted(
        [p for p in passengers if p["customer_id"] in SCENARIO_A_PASSENGERS],
        key=lambda p: order.get(p["customer_id"], 99),
    )
    print(f"Scenario A — processing {len(targets)} passengers: {[p['customer_id'] for p in targets]}")
    results = {}

    for i, pax in enumerate(targets, start=1):
        cid = pax["customer_id"]
        pnr = pax["pnr"]
        print(f"\n>>> [{i}/{len(targets)}] Scenario A for {cid} (PNR {pnr})...")

        if cid == CHOICE_ORIENTED_CUSTOMER_ID:
            out = process_scenario_a_choice_oriented(verbose=verbose)
            results[cid] = out
        else:
            result = run_irop_workflow(cid, pnr, SCENARIO_A, chat_message=None, verbose=verbose)
            results[cid] = {"pnr": pnr, "result": result, "scenario": SCENARIO_A}

        print(f"<<< Finished {cid}")

    return results


def run_scenario_b(
    verbose: bool = True,
    chat_message: str | None = None,
    chat_history: list[dict] | None = None,
    ensure_scenario_a: bool = True,
) -> dict:
    """Scenario B: chat/pull concierge for CUST-404 (agentic multi-turn)."""
    msg = chat_message or DEFAULT_SCRIPTED_CHAT
    print(f"\n>>> Scenario B (chat/pull) for {CHOICE_ORIENTED_CUSTOMER_ID}...")
    out = process_scenario_b_concierge(
        chat_message=msg,
        chat_history=chat_history,
        verbose=verbose,
        ensure_scenario_a=ensure_scenario_a,
    )
    print(f"<<< Finished Scenario B")
    return {CHOICE_ORIENTED_CUSTOMER_ID: out}
