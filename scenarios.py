"""Scenario runners for Push (NBA) and Pull (Concierge) IROP demos."""

from crewai_agentic_workflow import run_irop_workflow
from iceberg_tools import get_passengers_for_event

SCENARIO_A = "PUSH_NBA"
SCENARIO_B = "PULL_CONCIERGE"

DAVID_CUSTOMER_ID = "CUST-404"
DAVID_PNR = "PNR-404D"
DAVID_CHAT = (
    "My connection just got cut to 40 minutes, can you get me on something else "
    "and sort out lounge access while I wait?"
)

# Scenario A focuses on archetype divergence for these three passengers
SCENARIO_A_PASSENGERS = ["CUST-101", "CUST-202", "CUST-303"]


def run_scenario_a_push(verbose: bool = True) -> dict:
    """Proactive NBA: decide per passenger before they ask."""
    passengers = get_passengers_for_event()
    targets = [p for p in passengers if p["customer_id"] in SCENARIO_A_PASSENGERS]
    print(f"Found {len(targets)} passengers for Scenario A: {[p['customer_id'] for p in targets]}")
    results = {}
    for i, pax in enumerate(targets, start=1):
        cid = pax["customer_id"]
        pnr = pax["pnr"]
        print(f"\n>>> [{i}/{len(targets)}] Running 3-agent crew for {cid} (PNR {pnr})...")
        result = run_irop_workflow(cid, pnr, SCENARIO_A, chat_message=None, verbose=verbose)
        results[cid] = {"pnr": pnr, "result": result}
        print(f"<<< Finished {cid}")
    return results


def run_scenario_b_pull(verbose: bool = True) -> dict:
    """Concierge pull: David (CUST-404) initiates via chat."""
    print(f"\n>>> Running 3-agent crew for {DAVID_CUSTOMER_ID} (PNR {DAVID_PNR}) — concierge pull...")
    result = run_irop_workflow(
        DAVID_CUSTOMER_ID,
        DAVID_PNR,
        SCENARIO_B,
        chat_message=DAVID_CHAT,
        verbose=verbose,
    )
    print(f"<<< Finished {DAVID_CUSTOMER_ID}")
    return {DAVID_CUSTOMER_ID: {"pnr": DAVID_PNR, "result": result}}
