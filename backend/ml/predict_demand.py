import pandas as pd
import joblib

from sqlalchemy.orm import Session

from database import SessionLocal
from models.entities import DemandPrediction


DATA_FILE = "../data/processed/hospital_resource_features.csv"
MODEL_FILE = "forecasting_model.pkl"


def prepare_latest_features(df):

    df = df.copy()

    df["date"] = pd.to_datetime(df["date"])

    df = df.sort_values(
        by=["hospital_id", "resource_id", "date"]
    )

    group = df.groupby(
        ["hospital_id", "resource_id"]
    )

    df["lag_1"] = group["quantity_consumed"].shift(1)
    df["lag_2"] = group["quantity_consumed"].shift(2)
    df["lag_3"] = group["quantity_consumed"].shift(3)
    df["lag_7"] = group["quantity_consumed"].shift(7)

    df["rolling_mean_7"] = (
        group["quantity_consumed"]
        .transform(
            lambda x: x.shift(1).rolling(
                7,
                min_periods=3
            ).mean()
        )
    )

    df["rolling_std_7"] = (
        group["quantity_consumed"]
        .transform(
            lambda x: x.shift(1).rolling(
                7,
                min_periods=3
            ).std()
        )
    )

    df["day_of_week"] = df["date"].dt.dayofweek
    df["day_of_month"] = df["date"].dt.day
    df["month"] = df["date"].dt.month

    df["time_index"] = (
        df.groupby(
            ["hospital_id", "resource_id"]
        ).cumcount()
    )

    return df


def save_predictions(predictions, db: Session):

    for prediction in predictions:

        record = DemandPrediction(
            hospital_id=int(prediction["hospital_id"]),
            resource_id=int(prediction["resource_id"]),
            prediction_date=pd.Timestamp.now().date(),
            forecast_date=prediction["forecast_date"],
            predicted_quantity=float(
                prediction["predicted_quantity"]
            ),
            model_name=prediction["model_name"]
        )

        db.add(record)

    db.commit()


def main():

    data = pd.read_csv(DATA_FILE)

    package = joblib.load(MODEL_FILE)

    model = package["model"]
    features = package["features"]
    model_name = package["model_name"]

    prepared = prepare_latest_features(data)

    prepared = prepared.dropna(
        subset=features
    )

    latest = (
        prepared
        .groupby(
            ["hospital_id", "resource_id"]
        )
        .tail(1)
        .copy()
    )

    predictions = model.predict(
        latest[features]
    )

    prediction_records = []

    for (_, row), predicted_value in zip(
        latest.iterrows(),
        predictions
    ):

        forecast_date = (
            row["date"] + pd.Timedelta(days=1)
        ).date()

        prediction_records.append({
            "hospital_id": int(row["hospital_id"]),
            "resource_id": int(row["resource_id"]),
            "forecast_date": forecast_date,
            "predicted_quantity": predicted_value,
            "model_name": model_name
        })

    db = SessionLocal()

    try:

        save_predictions(
            prediction_records,
            db
        )

        print("\nPredictions saved to PostgreSQL.")

        for prediction in prediction_records:

            print(
                f"Hospital {prediction['hospital_id']} | "
                f"Resource {prediction['resource_id']} | "
                f"Forecast Date {prediction['forecast_date']} | "
                f"Demand {prediction['predicted_quantity']:.2f} | "
                f"Model {prediction['model_name']}"
            )

    except Exception as e:

        db.rollback()

        print(
            "Error saving predictions:",
            e
        )

    finally:

        db.close()


if __name__ == "__main__":
    main()