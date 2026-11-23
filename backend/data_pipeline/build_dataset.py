
import pandas as pd
from pathlib import Path

from database import SessionLocal
from models.entities import ConsumptionHistory


def build_dataset():

    db = SessionLocal()

    try:
        # Fetch consumption history directly from PostgreSQL
        records = (
            db.query(
                ConsumptionHistory.hospital_id,
                ConsumptionHistory.resource_id,
                ConsumptionHistory.consumption_date,
                ConsumptionHistory.quantity_consumed
            )
            .order_by(
                ConsumptionHistory.hospital_id,
                ConsumptionHistory.resource_id,
                ConsumptionHistory.consumption_date
            )
            .all()
        )

        if not records:
            raise ValueError("No consumption history found.")

        # Convert database records into a DataFrame
        df = pd.DataFrame(
            records,
            columns=[
                "hospital_id",
                "resource_id",
                "date",
                "quantity_consumed"
            ]
        )

        df["date"] = pd.to_datetime(df["date"])

        df["quantity_consumed"] = pd.to_numeric(
            df["quantity_consumed"],
            errors="coerce"
        )

        # Remove invalid records
        df = df.dropna(
            subset=[
                "hospital_id",
                "resource_id",
                "date",
                "quantity_consumed"
            ]
        )

        df = df[df["quantity_consumed"] >= 0]

        # Aggregate duplicate dates safely
        df = (
            df.groupby(
                ["hospital_id", "resource_id", "date"],
                as_index=False
            )["quantity_consumed"]
            .sum()
        )

        df = df.sort_values(
            ["hospital_id", "resource_id", "date"]
        ).reset_index(drop=True)

        # Save processed dataset
        backend_dir = Path(__file__).resolve().parent.parent

        output_dir = backend_dir / "data" / "processed"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "hospital_resource_consumption.csv"

        df.to_csv(output_file, index=False)

        print("\nDataset generated successfully!")
        print("Total records:", len(df))
        print("Hospitals:", df["hospital_id"].nunique())
        print("Resources:", df["resource_id"].nunique())
        print("Date range:", df["date"].min(), "to", df["date"].max())
        print("\nSaved at:", output_file)

        print("\nRecords per hospital and resource:")
        print(
            df.groupby(
                ["hospital_id", "resource_id"]
            ).size()
        )

    finally:
        db.close()


if __name__ == "__main__":
    build_dataset()
