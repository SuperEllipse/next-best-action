"""CrewAI 3-agent IROP workflow — profiles from Snowflake MCP, everything else from Iceberg."""

import os
from typing import Optional

from crewai import Agent, Crew, Process, Task

from iceberg_tools import (
    fetch_operational_context,
    log_execution_result,
    query_inventory,
    query_uplift_and_actions,
)
from snowflake_mcp import fetch_passenger_profile


def build_irop_crew(
    customer_id: str,
    pnr: str,
    scenario: str,
    chat_message: Optional[str] = None,
    verbose: bool = False,
) -> Crew:
    """Build the 3-agent crew for a single passenger IROP decision."""
    profile_summary = fetch_passenger_profile(customer_id, verbose=verbose)

    context_agent = Agent(
        role="Context and Signal Agent",
        goal="Enrich passenger context by combining Snowflake profile with Iceberg operational signals",
        backstory=(
            "You specialize in airline disruption context assembly. "
            "Passenger profiles come from Snowflake (already provided). "
            "Use Iceberg tools for flight events and chat signals."
        ),
        tools=[fetch_operational_context],
        verbose=verbose,
    )

    strategy_agent = Agent(
        role="Uplift and Strategy Agent",
        goal="Classify passenger archetype and recommend the optimal gesture strategy",
        backstory=(
            "You are an uplift modeling expert. Compare propensity vs uplift to avoid "
            "wasting gestures on Sure Things, invest in Persuadables, and avoid backfiring "
            "on Sleeping Dogs. Never recommend generic vouchers when direct rebooking is needed."
        ),
        tools=[query_uplift_and_actions],
        verbose=verbose,
    )

    fulfillment_agent = Agent(
        role="Fulfillment and Guardrail Agent",
        goal="Validate inventory, apply guardrails, execute the plan, and write audit log",
        backstory=(
            "You execute fulfillment actions and enforce guardrails. "
            "Check live inventory before confirming rebooks or lounge access. "
            "Reject actions that backfire (e.g., voucher for Sleeping Dog archetype). "
            "Always log the final decision to the audit table."
        ),
        tools=[query_inventory, log_execution_result],
        verbose=verbose,
    )

    chat_context = (
        f"\nPassenger chat message: {chat_message}"
        if chat_message
        else "\nNo chat message (proactive scenario)."
    )

    context_task = Task(
        description=(
            f"For customer {customer_id} (PNR {pnr}), scenario {scenario}:\n"
            f"Snowflake Profile (pre-fetched): {profile_summary}\n"
            f"Fetch operational events and chat signals from Iceberg.{chat_context}\n"
            "Extract any constraints (e.g., must land before 18:00, lounge needed)."
        ),
        expected_output="Enriched passenger context with profile summary, event details, and extracted constraints.",
        agent=context_agent,
    )

    strategy_task = Task(
        description=(
            f"Using the enriched context for {customer_id}, query uplift history and action shelf. "
            "Classify archetype (SURE_THING, PERSUADABLE, SLEEPING_DOG). "
            "Recommend one action from the shelf with uplift-based reasoning. "
            f"Scenario type: {scenario}."
        ),
        expected_output=(
            "Archetype classification, recommended action code, and uplift-based rationale "
            "explaining why this action maximizes retention without backfiring."
        ),
        agent=strategy_agent,
        context=[context_task],
    )

    fulfillment_task = Task(
        description=(
            f"For {customer_id} (PNR {pnr}), validate inventory for the recommended action. "
            "Apply guardrails: block voucher-only for SLEEPING_DOG, avoid expensive gestures "
            "for SURE_THING with zero uplift. Confirm or adjust the plan. "
            f"Log final decision to audit table with scenario='{scenario}'."
        ),
        expected_output=(
            "Inventory validation result, final action taken, guardrail notes, "
            "and confirmation that audit log was written."
        ),
        agent=fulfillment_agent,
        context=[strategy_task],
    )

    return Crew(
        agents=[context_agent, strategy_agent, fulfillment_agent],
        tasks=[context_task, strategy_task, fulfillment_task],
        process=Process.sequential,
        verbose=verbose,
    )


def run_irop_workflow(
    customer_id: str,
    pnr: str,
    scenario: str,
    chat_message: Optional[str] = None,
    verbose: bool = False,
) -> str:
    """Execute the full 3-agent IROP workflow for one passenger."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required.")
    crew = build_irop_crew(customer_id, pnr, scenario, chat_message, verbose)
    return str(crew.kickoff())
