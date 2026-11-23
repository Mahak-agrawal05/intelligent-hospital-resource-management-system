import pytest

from services.recommendation_priority import calculate_recommendation_priority


@pytest.mark.parametrize(
    ("shortage_risk", "wastage_risk", "criticality", "expected"),
    [
        (80, 10, "MEDIUM", "HIGH"),
        (10, 50, "MEDIUM", "MEDIUM"),
        (20, 20, "MEDIUM", "LOW"),
        (20, 20, "HIGH", "MEDIUM"),
        (50, 10, "HIGH", "HIGH"),
        (75, 0, "LOW", "HIGH"),
        (40, 0, "MEDIUM", "MEDIUM"),
        (39.99, 0, "MEDIUM", "LOW"),
        (0, 100, "LOW", "HIGH"),
        (0, 0, "LOW", "LOW"),
        (0, 0, " high ", "MEDIUM"),
        (0, 0, "medium", "LOW"),
    ],
)
def test_calculate_recommendation_priority(
    shortage_risk, wastage_risk, criticality, expected
):
    assert (
        calculate_recommendation_priority(
            shortage_risk=shortage_risk,
            wastage_risk=wastage_risk,
            criticality=criticality,
        )
        == expected
    )


@pytest.mark.parametrize("criticality", ["", "URGENT", "CRITICAL", "unknown"])
def test_invalid_criticality_is_rejected(criticality):
    with pytest.raises(ValueError, match="Invalid resource criticality"):
        calculate_recommendation_priority(
            shortage_risk=10,
            wastage_risk=10,
            criticality=criticality,
        )


@pytest.mark.parametrize(
    ("shortage_risk", "wastage_risk"),
    [
        (-0.01, 10),
        (100.01, 10),
        (10, -0.01),
        (10, 100.01),
    ],
)
def test_risk_percentages_outside_range_are_rejected(
    shortage_risk, wastage_risk
):
    with pytest.raises(ValueError):
        calculate_recommendation_priority(
            shortage_risk=shortage_risk,
            wastage_risk=wastage_risk,
            criticality="MEDIUM",
        )
