def calculate_shortage_risk(
    current_stock,
    predicted_daily_demand,
    lead_time_days,
    safety_stock
):
    """
    Calculate shortage risk using current stock,
    predicted demand, supplier lead time and safety stock.
    """

    # Validate inputs
    if current_stock < 0:
        raise ValueError("Current usable stock cannot be negative.")

    if predicted_daily_demand < 0:
        raise ValueError("Predicted daily demand cannot be negative.")

    if lead_time_days < 0 or safety_stock < 0:
        raise ValueError("Lead time and safety stock cannot be negative.")

    # Expected consumption during supplier lead time
    lead_time_demand = predicted_daily_demand * lead_time_days

    # Stock required during lead time plus safety stock
    required_stock = lead_time_demand + safety_stock

    # Difference between available and required stock
    stock_gap = current_stock - required_stock

    # Days current stock can support demand
    if predicted_daily_demand > 0:
        days_of_stock = current_stock / predicted_daily_demand
    else:
        days_of_stock = float("inf")

    # Determine risk level
    if current_stock <= safety_stock:
        risk_level = "CRITICAL"
    elif current_stock < required_stock:
        risk_level = "HIGH"
    elif current_stock < required_stock * 1.25:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "current_stock": current_stock,
        "predicted_daily_demand": predicted_daily_demand,
        "lead_time_days": lead_time_days,
        "safety_stock": safety_stock,
        "lead_time_demand": lead_time_demand,
        "required_stock": required_stock,
        "stock_gap": stock_gap,
        "days_of_stock": days_of_stock,
        "risk_level": risk_level
    }
