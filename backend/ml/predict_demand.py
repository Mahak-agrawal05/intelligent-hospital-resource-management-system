
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from database import SessionLocal
from models.entities import DemandPrediction


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "hospital_resource_consumption.csv"
)

MODEL_FILE = (
    BASE_DIR
    / "ml"
    / "artifacts"
    / "forecasting_model.pkl"
)

FORECAST_DAYS = 30


def generate_future_features(
    history,
    hospital_id,
    resource_id,
    forecast_date,
    time_index
):
    values = np.asarray(history, dtype=float)

    return {
        "hospital_id": hospital_id,
        "resource_id": resource_id,
        "lag_1": values[-1],
        "lag_2": values[-2],
        "lag_3": values[-3],
        "lag_7": values[-7],
        "rolling_mean_7": np.mean(values[-7:]),
        "rolling_mean_30": np.mean(values[-30:]),
        "rolling_std_7": np.std(values[-7:], ddof=1),
        "day_of_week": forecast_date.dayofweek,
        "day_of_month": forecast_date.day,
        "month": forecast_date.month,
        "time_index": time_index
    }


def generate_forecasts(model_package, data):

    model = model_package["model"]
    features = model_package["features"]
    model_name = model_package["model_name"]

    data["date"] = pd.to_datetime(data["date"])

    data = data.sort_values(
        ["hospital_id", "resource_id", "date"]
    )

    predictions = []

    groups = data.groupby(
        ["hospital_id", "resource_id"]
    )

    for (hospital_id, resource_id), group in groups:

        group = group.sort_values("date")

        history = group["quantity_consumed"].astype(float).tolist()

        if len(history) < 30:
            print(
                f"Skipping Hospital {hospital_id}, "
                f"Resource {resource_id}: insufficient history."
            )
            continue

        last_date = group["date"].iloc[-1]

        forecast_start = max(
            last_date + pd.Timedelta(days=1),
            pd.Timestamp.today().normalize()
        )

        time_index = len(group)

        for day in range(FORECAST_DAYS):

            forecast_date = forecast_start + pd.Timedelta(days=day)

            row = generate_future_features(
                history=history,
                hospital_id=int(hospital_id),
                resource_id=int(resource_id),
                forecast_date=forecast_date,
                time_index=time_index
            )

            input_df = pd.DataFrame(
                [row],
                columns=features
            )

            predicted_value = float(
                model.predict(input_df)[0]
            )

            predicted_value = max(0.0, predicted_value)

            predictions.append({
                "hospital_id": int(hospital_id),
                "resource_id": int(resource_id),
                "forecast_date": forecast_date.date(),
                "predicted_quantity": predicted_value,
                "model_name": model_name
            })

            # Use the predicted value to forecast the next day.
            history.append(predicted_value)
            time_index += 1

    return predictions


def save_predictions(predictions, db: Session):

    today = date.today()

    try:

        for prediction in predictions:

            existing = (
                db.query(DemandPrediction)
                .filter(
                    DemandPrediction.hospital_id
                    == prediction["hospital_id"],
                    DemandPrediction.resource_id
                    == prediction["resource_id"],
                    DemandPrediction.forecast_date
                    == prediction["forecast_date"]
                )
                .first()
            )

            if existing:

                existing.prediction_date = today
                existing.predicted_quantity = (
                    prediction["predicted_quantity"]
                )
                existing.model_name = prediction["model_name"]

            else:

                db.add(
                    DemandPrediction(
                        hospital_id=prediction["hospital_id"],
                        resource_id=prediction["resource_id"],
                        prediction_date=today,
                        forecast_date=prediction["forecast_date"],
                        predicted_quantity=prediction[
                            "predicted_quantity"
                        ],
                        model_name=prediction["model_name"]
                    )
                )

        db.commit()

    except Exception:
        db.rollback()
        raise


def main():

    print("\nLoading forecasting dataset...")

    if not DATA_FILE.exists():
        raise FileNotFoundError(DATA_FILE)

    if not MODEL_FILE.exists():
        raise FileNotFoundError(MODEL_FILE)

    data = pd.read_csv(DATA_FILE)

    package = joblib.load(MODEL_FILE)

    print("Model:", package["model_name"])
    print("Historical records:", len(data))

    predictions = generate_forecasts(package, data)

    if not predictions:
        print("No forecasts generated.")
        return

    db = SessionLocal()

    try:

        save_predictions(predictions, db)

        print("\nForecasts saved successfully!")

        print("Total predictions:", len(predictions))

        for prediction in predictions:

            print(
                f"Hospital {prediction['hospital_id']} | "
                f"Resource {prediction['resource_id']} | "
                f"Date {prediction['forecast_date']} | "
                f"Demand {prediction['predicted_quantity']:.2f}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()
