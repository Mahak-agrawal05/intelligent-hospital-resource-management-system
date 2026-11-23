
VALID_CRITICALITIES = {"HIGH", "MEDIUM", "LOW"}


def calculate_recommendation_priority(
    shortage_risk: float,
    wastage_risk: float,
    criticality: str = "MEDIUM",
) -> str:
    criticality = criticality.upper().strip()

    if criticality not in VALID_CRITICALITIES:
        raise ValueError("Invalid resource criticality.")

    if not 0 <= shortage_risk <= 100:
        raise ValueError("Shortage risk must be between 0 and 100.")

    if not 0 <= wastage_risk <= 100:
        raise ValueError("Wastage risk must be between 0 and 100.")

    highest_risk = max(shortage_risk, wastage_risk)

    # Base priority from the highest risk percentage.
    if highest_risk >= 75:
        priority = "HIGH"
    elif highest_risk >= 40:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    # High-criticality resources receive one-level escalation.
    if criticality == "HIGH":
        if priority == "LOW":
            priority = "MEDIUM"
        elif priority == "MEDIUM":
            priority = "HIGH"

    return priority
