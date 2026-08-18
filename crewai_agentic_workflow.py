"""CrewAI 3-agent IROP workflow — profiles from Snowflake MCP, everything else from Iceberg."""

import json
import os
from typing import Optional

from crewai import Agent, Crew, Process, Task

from iceberg_tools import (
    append_chat_signal_tool,
    confirm_passenger_choice,
    fetch_operational_context,
    log_execution_result,
    place_flight_holds,
    query_inventory,
    query_uplift_and_actions,
    read_prior_concierge_audit,
    read_push_staging,
    re_hold_alternate_flights,
)
from snowflake_mcp import fetch_passenger_profile


def _format_chat_history(chat_history: Optional[list[dict]]) -> str:
    if not chat_history:
        return "(no prior turns — this is the first concierge message)"
    lines = []
    for turn in chat_history:
        role = turn.get("role", "passenger").upper()
        text = turn.get("text") or turn.get("message") or ""
        lines.append(f"[{role}]: {text}")
    return "\n".join(lines)


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
            "Classify archetype (SURE_THING, PERSUADABLE, SLEEPING_DOG, CHOICE_ORIENTED). "
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


def build_choice_oriented_scenario_a_crew(
    customer_id: str,
    pnr: str,
    profile_summary: str,
    verbose: bool = False,
) -> Crew:
    """Scenario A crew path for Choice-Oriented passenger — HOLD_AND_PROMPT, not auto-rebook."""
    strategist = Agent(
        role="Uplift and Strategy Agent",
        goal="Recommend HOLD_AND_PROMPT for Choice-Oriented executives — never force auto-rebook",
        backstory=(
            "Passenger is CHOICE_ORIENTED: high-value, schedule-sensitive, prefers control. "
            "Scenario A must NOT auto-rebook. Pre-hold alternate flights and invite chat (Scenario B)."
        ),
        tools=[query_uplift_and_actions, place_flight_holds],
        verbose=verbose,
    )
    task = Task(
        description=(
            f"For {customer_id} ({pnr}), Scenario A (Push/NBA):\n"
            f"Profile: {profile_summary[:600]}\n"
            "Classify as CHOICE_ORIENTED. Recommend ACT-005 HOLD_AND_PROMPT. "
            "Explain why auto-rebook would backfire for this executive."
        ),
        expected_output="Archetype CHOICE_ORIENTED and HOLD_AND_PROMPT rationale.",
        agent=strategist,
    )
    return Crew(agents=[strategist], tasks=[task], verbose=verbose)


def build_scenario_b_agentic_crew(
    customer_id: str,
    pnr: str,
    profile_summary: str,
    chat_message: str,
    chat_history: Optional[list[dict]] = None,
    case_id: str = "",
    verbose: bool = False,
) -> Crew:
    """
    Scenario B — full 3-agent concierge workflow for multi-turn free-form chat.
    Agents interpret the full conversation; no hardcoded flight choice in prompts.
    """
    history_text = _format_chat_history(chat_history)

    context_agent = Agent(
        role="Context and Signal Agent",
        goal="Assemble full conversational context from Iceberg signals, staging, and prior decisions",
        backstory=(
            "You read operational events, unstructured chat history from the dashboard session, "
            "and Scenario A staging for the current case_id only. "
            "Ignore prior concierge audit rows from earlier demo runs or other case_ids. "
            "Extract hard constraints (e.g. arrival before 18:00) and note when the passenger "
            "revokes or changes constraints in a later turn."
        ),
        tools=[
            fetch_operational_context,
            read_push_staging,
            append_chat_signal_tool,
        ],
        verbose=verbose,
    )

    strategy_agent = Agent(
        role="Concierge Strategy Agent",
        goal="Interpret passenger intent from the full conversation and recommend a fulfillment plan",
        backstory=(
            "You serve CHOICE_ORIENTED executives in Scenario B pull/concierge chat. "
            "Base decisions on the dashboard conversation history and latest message — NOT stale audit rows. "
            "Turn 1 with an 8 PM dinner and must land before 18:00 → EK372 + quiet workspace. "
            "Turn 2 only when the passenger explicitly cancels dinner or asks for a later flight → EK380 + lounge."
        ),
        tools=[query_uplift_and_actions, query_inventory],
        verbose=verbose,
    )

    fulfillment_agent = Agent(
        role="Fulfillment and Guardrail Agent",
        goal="Execute the chosen rebook and amenities using live Iceberg inventory",
        backstory=(
            "You confirm inventory holds, release unchosen flights, and summarize fulfillment. "
            "EK372 arrives SIN ~17:15; EK380 arrives SIN ~21:30. "
            "Use confirm_passenger_choice only after validating seats and amenities. "
            "Do not write audit rows — the orchestrator logs the final decision once."
        ),
        tools=[
            query_inventory,
            confirm_passenger_choice,
            re_hold_alternate_flights,
        ],
        verbose=verbose,
    )

    context_task = Task(
        description=(
            f"Customer {customer_id}, PNR {pnr}, Scenario B PULL_CONCIERGE, case_id={case_id or 'unknown'}.\n"
            f"Snowflake profile (pre-fetched): {profile_summary[:800]}\n\n"
            f"Full conversation history:\n{history_text}\n\n"
            f"Latest passenger message:\n{chat_message}\n\n"
            "Fetch Iceberg operational context and read Scenario A staging for this case_id only. "
            "Do not treat prior concierge audit rows from other sessions as current intent. "
            "Summarize active constraints, revoked constraints, and amenity preferences."
        ),
        expected_output=(
            "Context brief: disruption details, staging status, constraint timeline across turns, "
            "and amenity needs (quiet workspace vs lounge rest)."
        ),
        agent=context_agent,
    )

    strategy_task = Task(
        description=(
            f"Using the context brief for {customer_id}, query uplift/action shelf and live inventory.\n"
            "Decide the best fulfillment plan based on the FULL chat — latest message may override earlier constraints.\n"
            "Examples (for guidance only — decide from actual chat):\n"
            "- Turn 1 with dinner before 18:00 → prefer earlier arrival + quiet work pod\n"
            "- Turn 2 dinner cancelled + wants rest → prefer later flight + extended lounge\n"
            "State chosen_flight, seat preference, amenity, and action_code."
        ),
        expected_output=(
            "Recommended plan: chosen_flight, seat, amenity, action_code, and rationale "
            "referencing specific phrases from the passenger's messages."
        ),
        agent=strategy_agent,
        context=[context_task],
    )

    fulfillment_task = Task(
        description=(
            f"Execute the strategy plan for {customer_id} ({pnr}).\n"
            "Query inventory, re-hold alternates if needed, confirm the chosen flight, release others.\n"
            "Do not call any audit logging tools.\n\n"
            "End your final answer with a JSON block exactly in this shape:\n"
            "```json\n"
            + json.dumps(
                {
                    "chosen_flight": "EK372 or EK380",
                    "seat": "e.g. 3K or 12A",
                    "amenity": "e.g. Quiet Pod #4 or Extended Business Lounge",
                    "action_code": "CONFIRM_REBOOK_QUIET_POD or CONFIRM_REBOOK_LATER_LOUNGE",
                    "passenger_reply": "Warm concierge confirmation in 2-3 sentences",
                    "reasoning_summary": "One paragraph explaining why this choice fits the conversation",
                },
                indent=2,
            )
            + "\n```"
        ),
        expected_output=(
            "Inventory confirmation and JSON block with chosen_flight, seat, "
            "amenity, action_code, passenger_reply, reasoning_summary."
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


def run_choice_oriented_scenario_a_crew(
    customer_id: str,
    pnr: str,
    profile_summary: str,
    verbose: bool = False,
) -> str:
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required.")
    crew = build_choice_oriented_scenario_a_crew(customer_id, pnr, profile_summary, verbose)
    return str(crew.kickoff())


def run_scenario_b_concierge_crew(
    customer_id: str,
    pnr: str,
    profile_summary: str,
    chat_message: str,
    chat_history: Optional[list[dict]] = None,
    case_id: str = "",
    verbose: bool = False,
) -> str:
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required.")
    crew = build_scenario_b_agentic_crew(
        customer_id,
        pnr,
        profile_summary,
        chat_message,
        chat_history=chat_history,
        case_id=case_id,
        verbose=verbose,
    )
    return str(crew.kickoff())
