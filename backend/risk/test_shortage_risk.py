from shortage_risk import calculate_shortage_risk


result = calculate_shortage_risk(
    current_stock=1100,
    predicted_daily_demand=250,
    lead_time_days=7,
    safety_stock=300
)

print("\n--- SHORTAGE RISK ANALYSIS ---")

for key, value in result.items():
    print(f"{key}: {value}")