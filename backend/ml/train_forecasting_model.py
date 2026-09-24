import pandas as pd
import joblib

from sklearn.model_selection import TimeSeriesSplit

from .forecasting import (
    prepare_forecasting_data,
    FEATURES,
    TARGET,
    get_models,
    calculate_metrics
)


DATA_FILE = "../data/processed/hospital_resource_features.csv"

MODEL_FILE = "forecasting_model.pkl"


def main():

    # -----------------------------------------
    # 1. Load processed data
    # -----------------------------------------

    df = pd.read_csv(DATA_FILE)

    # -----------------------------------------
    # 2. Prepare forecasting features
    # -----------------------------------------

    df = prepare_forecasting_data(df)

    print("\nForecasting dataset:")
    print(df.shape)

    if len(df) < 10:
        raise ValueError(
            "Not enough historical data for forecasting."
        )

    X = df[FEATURES]
    y = df[TARGET]

    # -----------------------------------------
    # 3. Time-aware train/test split
    # -----------------------------------------

    split_index = int(len(df) * 0.8)

    X_train = X.iloc[:split_index]
    X_test = X.iloc[split_index:]

    y_train = y.iloc[:split_index]
    y_test = y.iloc[split_index:]

    print("\nTraining rows:", len(X_train))
    print("Testing rows:", len(X_test))

    # -----------------------------------------
    # 4. Compare models
    # -----------------------------------------

    models = get_models()

    results = {}

    for name, model in models.items():

        model.fit(X_train, y_train)

        predictions = model.predict(X_test)

        metrics = calculate_metrics(
            y_test,
            predictions
        )

        results[name] = metrics

        print(f"\n{name}")
        print("-------------------------")
        print(f"MAE  : {metrics['MAE']:.2f}")
        print(f"RMSE : {metrics['RMSE']:.2f}")
        print(f"MAPE : {metrics['MAPE']:.2f}%")

    # -----------------------------------------
    # 5. Select model using RMSE
    # -----------------------------------------

    best_model_name = min(
        results,
        key=lambda name: results[name]["RMSE"]
    )

    best_model = models[best_model_name]

    print("\nBest-supported model:")
    print(best_model_name)

    # -----------------------------------------
    # 6. Retrain selected model on all data
    # -----------------------------------------

    best_model.fit(X, y)

    # -----------------------------------------
    # 7. Save model
    # -----------------------------------------

    joblib.dump(
        {
            "model": best_model,
            "model_name": best_model_name,
            "features": FEATURES
        },
        MODEL_FILE
    )

    print(
        f"\nModel saved to: {MODEL_FILE}"
    )


if __name__ == "__main__":
    main()