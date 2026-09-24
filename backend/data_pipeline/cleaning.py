import pandas as pd


def clean_inventory_data(file_path: str) -> pd.DataFrame:
    # 1. Load raw CSV
    df = pd.read_csv(file_path)

    # 2. Remove completely empty rows
    df = df.dropna(how="all")

    # 3. Remove duplicate records
    df = df.drop_duplicates()

    # 4. Convert date columns
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["expiry_date"] = pd.to_datetime(
        df["expiry_date"],
        errors="coerce"
    )

    # 5. Numeric columns
    numeric_columns = [
        "hospital_id",
        "resource_id",
        "quantity_consumed",
        "current_quantity",
        "reserved_quantity",
        "reorder_level",
        "safety_stock",
        "lead_time_days"
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # 6. Remove rows with critical missing values
    critical_columns = [
        "hospital_id",
        "resource_id",
        "date",
        "quantity_consumed"
    ]

    df = df.dropna(subset=critical_columns)

    # 7. Remove invalid negative values
    non_negative_columns = [
        "quantity_consumed",
        "current_quantity",
        "reserved_quantity",
        "reorder_level",
        "safety_stock",
        "lead_time_days"
    ]

    for column in non_negative_columns:
        df = df[df[column] >= 0]

    # 8. Ensure reserved stock does not exceed current stock
    df = df[
        df["reserved_quantity"] <= df["current_quantity"]
    ]

    # 9. Sort data
    df = df.sort_values(
        by=["hospital_id", "resource_id", "date"]
    )

    # 10. Reset index
    df = df.reset_index(drop=True)

    return df