
import pandas as pd


TARGET = "quantity_consumed"

FEATURES = [
    "hospital_id",
    "resource_id",
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_7",
    "rolling_mean_7",
    "rolling_mean_30",
    "rolling_std_7",
    "day_of_week",
    "day_of_month",
    "month",
    "time_index"
]


def prepare_forecasting_data(df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()

    df["date"] = pd.to_datetime(df["date"])

    df = df.sort_values(
        ["hospital_id", "resource_id", "date"]
    ).reset_index(drop=True)

    group = df.groupby(["hospital_id", "resource_id"])[TARGET]

    # Historical lag features
    for lag in [1, 2, 3, 7]:
        df[f"lag_{lag}"] = group.shift(lag)

    # Rolling features use previous observations only
    df["rolling_mean_7"] = group.transform(
        lambda x: x.shift(1).rolling(7, min_periods=7).mean()
    )

    df["rolling_mean_30"] = group.transform(
        lambda x: x.shift(1).rolling(30, min_periods=30).mean()
    )

    df["rolling_std_7"] = group.transform(
        lambda x: x.shift(1).rolling(7, min_periods=7).std()
    )

    # Calendar features
    df["day_of_week"] = df["date"].dt.dayofweek
    df["day_of_month"] = df["date"].dt.day
    df["month"] = df["date"].dt.month

    df["time_index"] = (
        df.groupby(["hospital_id", "resource_id"]).cumcount()
    )

    # Remove rows without sufficient historical observations
    df = df.dropna(subset=FEATURES)

    return df.reset_index(drop=True)
