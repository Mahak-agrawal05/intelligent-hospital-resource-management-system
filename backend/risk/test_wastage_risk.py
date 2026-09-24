from wastage_risk import calculate_wastage_risk


def test_wastage_risk():
    result = calculate_wastage_risk(
        current_stock=5000,
        predicted_daily_demand=125,
        days_until_expiry=10
    )

    assert result["expected_consumption"] == 1250
    assert result["expected_wastage"] == 3750
    assert result["wastage_percentage"] == 75
    assert result["risk_level"] == "HIGH"