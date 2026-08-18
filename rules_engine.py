"""Static rules-engine contrast for David — traditional propensity model vs agentic workflow."""


def rules_engine_decision(customer_id: str = "CUST-404", pnr: str = "PNR-404D") -> dict:
    """Simulate a rules-based propensity model (non-agentic baseline)."""
    return {
        "system": "Standard Propensity Model (Rules-Based)",
        "customer_id": customer_id,
        "pnr": pnr,
        "inputs": {
            "loyalty_tier": "PLATINUM",
            "misconnect_risk": True,
            "rule": "IF high_tier AND misconnect THEN auto_rebook(latest_available) + meal_voucher",
        },
        "action_taken": "Auto-rebook on EK380 + email $50 meal voucher",
        "operational_result": "Failure: lands 9:30 PM SIN — misses 8:00 PM client dinner",
        "customer_result": "High-value passenger receives insulting voucher; schedule constraint ignored",
        "flight_chosen": "EK380",
        "arrival_local": "21:30",
        "voucher_usd": 50,
    }


def agentic_decision_summary() -> dict:
    """Expected agentic outcome for side-by-side executive contrast."""
    return {
        "system": "Agentic Workflow (Context + Unstructured Reasoning)",
        "turn_1": {
            "passenger_says": "8 PM dinner in Singapore — cannot land after 6 PM; need quiet workspace",
            "agent_does": "Reads constraints, confirms EK372 + Quiet Pod #4",
            "flight": "EK372",
            "arrival": "17:15",
        },
        "turn_2": {
            "passenger_says": "Dinner cancelled — I'd like a few hours rest and the later flight",
            "agent_does": "Re-reads full chat, lifts prior <18:00 constraint, confirms EK380 + extended lounge",
            "flight": "EK380",
            "arrival": "21:30",
        },
        "action_taken": "Multi-turn: hold options → EK372 + Quiet Pod, then adapts to EK380 + lounge rest",
        "operational_result": "Turn 1: lands 5:15 PM SIN. Turn 2: honors change-of-mind with lounge rest.",
        "customer_result": "Schedule constraints honored when active; flexible when passenger changes plans",
        "flight_chosen": "EK372 → EK380 (on follow-up)",
        "arrival_local": "17:15 → 21:30",
        "amenity": "Quiet Pod #4 → Extended Business Lounge",
    }
