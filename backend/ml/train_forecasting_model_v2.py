
import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, mean_squared_error

from ml.forecasting import get_models
from ml.forecasting_features import (
    prepare_forecasting_data,
    FEATURES,
    TARGET
)


# --------------------------------------------------
# FILE PATHS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "hospital_resource_consumption.csv"
)

MODEL_DIR = BASE_DIR / "ml" / "artifacts"

MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_FILE = MODEL_DIR / "forecasting_model.pkl"
METRICS_FILE = MODEL_DIR / "forecasting_metrics.json"


# --------------------------------------------------
# METRICS
# --------------------------------------------------

def calculate_metrics(y_true, y_pred):

    mae = mean_absolute_error(y_true, y_pred)

    rmse = np.sqrt(
        mean_squared_error(y_true, y_pred)
    )

    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    non_zero = y_true != 0

    if non_zero.any():
        mape = np.mean(
            np.abs(
                (y_true[non_zero] - y_pred[non_zero])
                / y_true[non_zero]
            )
        ) * 100
    else:
        mape = None

    return {
        "MAE": float(mae),
        "RMSE": float(rmse),
        "MAPE": float(mape) if mape is not None else None
    }


# --------------------------------------------------
# MAIN TRAINING
# --------------------------------------------------

def main():

    print("\nLoading PostgreSQL-generated dataset...")

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_FILE}"
        )

    df = pd.read_csv(DATA_FILE)

    df = prepare_forecasting_data(df)

    if len(df) < 50:
        raise ValueError(
            "Not enough historical data for model training."
        )

    X = df[FEATURES]
    y = df[TARGET]

    # Chronological 80/20 split.
    # Do not randomly shuffle time-series observations.
    split_index = int(len(df) * 0.8)

    X_train = X.iloc[:split_index]
    X_test = X.iloc[split_index:]

    y_train = y.iloc[:split_index]
    y_test = y.iloc[split_index:]

    print("\nDataset shape:", df.shape)
    print("Training rows:", len(X_train))
    print("Testing rows:", len(X_test))

    # --------------------------------------------------
    # TRAIN AND EVALUATE MODELS
    # --------------------------------------------------

    models = get_models()

    results = {}
    trained_models = {}

    for name, model in models.items():

        print(f"\nTraining {name}...")

        candidate = clone(model)

        candidate.fit(X_train, y_train)

        predictions = candidate.predict(X_test)

        predictions = np.maximum(predictions, 0)

        metrics = calculate_metrics(
            y_test,
            predictions
        )

        results[name] = metrics
        trained_models[name] = candidate

        print("MAE :", round(metrics["MAE"], 2))
        print("RMSE:", round(metrics["RMSE"], 2))
        print("MAPE:", round(metrics["MAPE"], 2)
              if metrics["MAPE"] is not None else "N/A")

    # --------------------------------------------------
    # SELECT BEST MODEL
    # --------------------------------------------------

    best_model_name = min(
        results,
        key=lambda name: results[name]["RMSE"]
    )

    best_metrics = results[best_model_name]

    print("\nBest model:", best_model_name)

    # --------------------------------------------------
    # TRAIN FINAL MODEL ON ALL AVAILABLE DATA
    # --------------------------------------------------

    final_model = clone(models[best_model_name])

    final_model.fit(X, y)

    # --------------------------------------------------
    # SAVE MODEL AND METRICS
    # --------------------------------------------------

    package = {
        "model": final_model,
        "model_name": best_model_name,
        "features": FEATURES,
        "metrics": best_metrics,
        "training_rows": len(X),
        "test_rows": len(X_test),
        "trained_on": pd.Timestamp.now().isoformat()
    }

    # This is the initial baseline model.
    # Do not overwrite an existing deployed model here.
    if MODEL_FILE.exists():

        print(
            "\nA model already exists. "
            "Skipping deployment to protect it."
        )

    else:

        joblib.dump(package, MODEL_FILE)

        print("\nInitial baseline model saved:", MODEL_FILE)

    with open(METRICS_FILE, "w", encoding="utf-8") as file:

        json.dump(
            {
                "model_comparison": results,
                "best_model": best_model_name,
                "best_metrics": best_metrics,
                "training_rows": len(X_train),
                "testing_rows": len(X_test),
                "total_rows": len(df)
            },
            file,
            indent=4
        )

    print("\nMetrics saved:", METRICS_FILE)

    print("\nModel training completed successfully!")


if __name__ == "__main__":
    main()
