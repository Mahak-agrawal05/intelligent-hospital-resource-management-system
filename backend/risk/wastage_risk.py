def calculate_wastage_risk(
    current_stock,
    predicted_daily_demand,
    days_until_expiry
):
    """
    Calculate wastage/expiry risk using current stock,
    predicted daily demand and remaining shelf life.
    """

    # Expected consumption before expiry
    expected_consumption = (
        predicted_daily_demand * days_until_expiry
    )

    # Stock that may remain unused before expiry
    expected_wastage = max(
        0,
        current_stock - expected_consumption
    )

    # Percentage of stock expected to be wasted
    if current_stock > 0:
        wastage_percentage = (
            expected_wastage / current_stock
        ) * 100
    else:
        wastage_percentage = 0

    # Determine risk level
    if days_until_expiry <= 7 and expected_wastage > 0:
        risk_level = "CRITICAL"

    elif expected_wastage >= current_stock * 0.50:
        risk_level = "HIGH"

    elif expected_wastage > 0:
        risk_level = "MEDIUM"

    else:
        risk_level = "LOW"

    return {
        "current_stock": current_stock,
        "predicted_daily_demand": predicted_daily_demand,
        "days_until_expiry": days_until_expiry,
        "expected_consumption": expected_consumption,
        "expected_wastage": expected_wastage,
        "wastage_percentage": wastage_percentage,
        "risk_level": risk_level
    }