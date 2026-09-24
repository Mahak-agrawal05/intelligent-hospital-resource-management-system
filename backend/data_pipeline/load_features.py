import pandas as pd
from sqlalchemy.orm import Session

from database import SessionLocal


FEATURE_FILE = "../data/processed/hospital_resource_features.csv"


def load_features():
    df = pd.read_csv(FEATURE_FILE)

    # Convert date columns to proper datetime values
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["expiry_date"] = pd.to_datetime(
        df["expiry_date"]
    ).dt.date

    db: Session = SessionLocal()

    try:
        df.to_sql(
            "processed_resource_features",
            con=db.bind,
            if_exists="append",
            index=False
        )

        db.commit()

        print(
            f"Successfully loaded {len(df)} rows "
            "into processed_resource_features."
        )

    except Exception as e:
        db.rollback()
        print("Error while loading features:", e)

    finally:
        db.close()


if __name__ == "__main__":
    load_features()