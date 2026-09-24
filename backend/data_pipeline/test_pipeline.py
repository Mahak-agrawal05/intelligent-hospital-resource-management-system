from cleaning import clean_inventory_data
from feature_engineering import create_features


RAW_FILE = "../data/raw/hospital_resource_data.csv"


df = clean_inventory_data(RAW_FILE)

print("\n--- CLEAN DATA ---")
print(df.shape)

df = create_features(df)

print("\n--- FEATURE ENGINEERED DATA ---")
print(df.shape)

print("\n--- FEATURES ---")
print(
    df[
        [
            "hospital_id",
            "resource_id",
            "date",
            "quantity_consumed",
            "avg_consumption_7d",
            "avg_consumption_30d",
            "days_of_stock_remaining",
            "days_until_expiry",
            "stock_vs_safety_stock",
            "consumption_trend",
            "below_reorder_level",
            "expiry_risk",
            "stockout_risk"
        ]
    ].tail(10)
)

OUTPUT_FILE = "../data/processed/hospital_resource_features.csv"

df.to_csv(
    OUTPUT_FILE,
    index=False
)

print(f"\nProcessed dataset saved to: {OUTPUT_FILE}")