import pandas as pd
import numpy as np

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

from sklearn.metrics import mean_absolute_error, mean_squared_error


TARGET = "quantity_consumed"


def prepare_forecasting_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["date"] = pd.to_datetime(df["date"])

    df = df.sort_values(
        by=["hospital_id", "resource_id", "date"]
    )

    group = df.groupby(
        ["hospital_id", "resource_id"]
    )

    # Previous consumption values
    df["lag_1"] = group[TARGET].shift(1)
    df["lag_2"] = group[TARGET].shift(2)
    df["lag_3"] = group[TARGET].shift(3)
    df["lag_7"] = group[TARGET].shift(7)

    # Historical rolling average.
    # shift(1) prevents today's target from leaking into the feature.
    df["rolling_mean_7"] = (
        group[TARGET]
        .transform(
            lambda x: x.shift(1).rolling(7, min_periods=3).mean()
        )
    )

    # Historical rolling standard deviation
    df["rolling_std_7"] = (
        group[TARGET]
        .transform(
            lambda x: x.shift(1).rolling(7, min_periods=3).std()
        )
    )

    # Calendar features
    df["day_of_week"] = df["date"].dt.dayofweek
    df["day_of_month"] = df["date"].dt.day
    df["month"] = df["date"].dt.month

    # Simple time trend
    df["time_index"] = (
        df.groupby(
            ["hospital_id", "resource_id"]
        ).cumcount()
    )

    # Remove rows where insufficient history exists
    df = df.dropna(
        subset=[
            "lag_1",
            "lag_2",
            "lag_3",
            "lag_7",
            "rolling_mean_7"
        ]
    )

    return df.reset_index(drop=True)


FEATURES = [
    "hospital_id",
    "resource_id",
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_7",
    "rolling_mean_7",
    "rolling_std_7",
    "day_of_week",
    "day_of_month",
    "month",
    "time_index"
]


def calculate_metrics(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)

    rmse = np.sqrt(
        mean_squared_error(y_true, y_pred)
    )

    # MAPE with protection against zero actual values
    y_true_array = np.asarray(y_true)
    y_pred_array = np.asarray(y_pred)

    non_zero = y_true_array != 0

    if non_zero.any():
        mape = np.mean(
            np.abs(
                (
                    y_true_array[non_zero]
                    - y_pred_array[non_zero]
                )
                / y_true_array[non_zero]
            )
        ) * 100
    else:
        mape = np.nan

    return {
        "MAE": mae,
        "RMSE": rmse,
        "MAPE": mape
    }


def get_models():
    return {
        "Linear Regression": LinearRegression(),

        "Random Forest": RandomForestRegressor(
            n_estimators=200,
            random_state=42,
            max_depth=8
        ),

        "XGBoost": XGBRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            objective="reg:squarederror",
            random_state=42
        )
    }