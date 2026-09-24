import pandas as pd
import numpy as np


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Make sure data is sorted chronologically
    df = df.sort_values(
        by=["hospital_id", "resource_id", "date"]
    )

    # --------------------------------------------------
    # 1. Recent consumption averages
    # --------------------------------------------------

    group = df.groupby(
        ["hospital_id", "resource_id"]
    )

    df["avg_consumption_7d"] = (
        group["quantity_consumed"]
        .transform(lambda x: x.rolling(7, min_periods=1).mean())
    )

    # 30-day average is calculated only when enough
    # historical observations are available.
    df["avg_consumption_30d"] = (
        group["quantity_consumed"]
        .transform(lambda x: x.rolling(30, min_periods=7).mean())
    )

    # --------------------------------------------------
    # 2. Days of stock remaining
    # --------------------------------------------------

    df["days_of_stock_remaining"] = np.where(
        df["avg_consumption_7d"] > 0,
        df["current_quantity"] / df["avg_consumption_7d"],
        np.inf
    )

    # --------------------------------------------------
    # 3. Days until expiry
    # --------------------------------------------------

    df["days_until_expiry"] = (
        df["expiry_date"] - df["date"]
    ).dt.days

    # --------------------------------------------------
    # 4. Stock compared with safety stock
    # --------------------------------------------------

    df["stock_vs_safety_stock"] = (
        df["current_quantity"] - df["safety_stock"]
    )

    # --------------------------------------------------
    # 5. Consumption trend
    # --------------------------------------------------

    df["previous_7d_avg"] = (
        group["quantity_consumed"]
        .transform(
            lambda x: x.shift(7).rolling(7, min_periods=3).mean()
        )
    )

    df["consumption_trend"] = np.where(
        df["previous_7d_avg"].notna()
        & (df["previous_7d_avg"] > 0),
        (
            (df["avg_consumption_7d"] - df["previous_7d_avg"])
            / df["previous_7d_avg"]
        ) * 100,
        0
    )

    # --------------------------------------------------
    # 6. Reorder status
    # --------------------------------------------------

    df["below_reorder_level"] = (
        df["current_quantity"] < df["reorder_level"]
    ).astype(int)

    # --------------------------------------------------
    # 7. Expiry risk indicator
    # --------------------------------------------------

    df["expiry_risk"] = (
        df["days_until_expiry"] <= 30
    ).astype(int)

    # --------------------------------------------------
    # 8. Stockout risk indicator
    # --------------------------------------------------

    df["stockout_risk"] = (
        df["days_of_stock_remaining"]
        <= df["lead_time_days"]
    ).astype(int)

    # Replace infinite values with NaN
    df["days_of_stock_remaining"] = (
        df["days_of_stock_remaining"]
        .replace([np.inf, -np.inf], np.nan)
    )

    return df.reset_index(drop=True)