
import unittest
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models.entities import (
    Hospital,
    Resource,
    Inventory,
    ResourceBatch,
    ConsumptionHistory,
)
from services.entity_service import create_consumption


class InventoryTransactionTests(unittest.TestCase):

    def setUp(self):
        # A fresh in-memory database for every test.
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        Base.metadata.create_all(bind=self.engine)

        TestSession = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

        self.db = TestSession()

        hospital = Hospital(
            hospital_name="Test Hospital",
            location="Test Location",
            hospital_type="General",
        )

        resource = Resource(
            resource_name="Test Medicine",
            category="Medicine",
            unit="Units",
            reorder_level=10,
            safety_stock=5,
            lead_time_days=2,
        )

        self.db.add_all([hospital, resource])
        self.db.flush()

        self.inventory = Inventory(
            hospital_id=hospital.hospital_id,
            resource_id=resource.resource_id,
            current_quantity=0,
            reserved_quantity=0,
            usable_quantity=0,
        )

        self.db.add(self.inventory)
        self.db.flush()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def add_batch(self, number, quantity, reserved, expiry):
        batch = ResourceBatch(
            inventory_id=self.inventory.inventory_id,
            batch_number=number,
            quantity=quantity,
            reserved_quantity=reserved,
            expiry_date=expiry,
        )

        self.db.add(batch)
        self.db.flush()

        self.inventory.current_quantity += quantity
        self.inventory.reserved_quantity += reserved
        self.inventory.usable_quantity += quantity - reserved

        self.db.commit()
        self.db.refresh(batch)

        return batch

    def consume(self, quantity):
        return create_consumption(
            db=self.db,
            hospital_id=self.inventory.hospital_id,
            resource_id=self.inventory.resource_id,
            consumption_date=date.today(),
            quantity_consumed=quantity,
        )

    def test_1_fefo_multiple_batches(self):
        today = date.today()

        first = self.add_batch(
            "BATCH-1", 3, 0, today + timedelta(days=5)
        )
        second = self.add_batch(
            "BATCH-2", 10, 0, today + timedelta(days=15)
        )

        result = self.consume(5)

        self.db.refresh(first)
        self.db.refresh(second)

        self.assertEqual(
            [a["batch_id"] for a in result["batch_allocations"]],
            [first.batch_id, second.batch_id],
        )
        self.assertEqual(first.quantity, 0)
        self.assertEqual(second.quantity, 8)

    def test_2_reserved_stock_protection(self):
        today = date.today()

        first = self.add_batch(
            "RESERVED-1", 10, 7, today + timedelta(days=5)
        )
        second = self.add_batch(
            "RESERVED-2", 10, 0, today + timedelta(days=10)
        )

        result = self.consume(4)

        self.db.refresh(first)
        self.db.refresh(second)

        self.assertEqual(first.quantity, 7)
        self.assertEqual(first.reserved_quantity, 7)
        self.assertEqual(second.quantity, 9)
        self.assertEqual(result["quantity_consumed"], 4)

    def test_3_expired_batch_exclusion(self):
        today = date.today()

        expired = self.add_batch(
            "EXPIRED", 10, 0, today - timedelta(days=1)
        )
        valid = self.add_batch(
            "VALID", 5, 0, today + timedelta(days=10)
        )

        result = self.consume(3)

        self.db.refresh(expired)
        self.db.refresh(valid)

        self.assertEqual(expired.quantity, 10)
        self.assertEqual(valid.quantity, 2)
        self.assertEqual(
            result["batch_allocations"][0]["batch_id"],
            valid.batch_id,
        )

    def test_4_insufficient_stock_rejected(self):
        today = date.today()

        batch = self.add_batch(
            "LIMITED", 3, 0, today + timedelta(days=5)
        )

        with self.assertRaises(ValueError):
            self.consume(5)

        self.db.refresh(batch)
        self.db.refresh(self.inventory)

        self.assertEqual(batch.quantity, 3)
        self.assertEqual(self.inventory.current_quantity, 3)

        history_count = (
            self.db.query(ConsumptionHistory).count()
        )
        self.assertEqual(history_count, 0)

    def test_5_inventory_batch_reconciliation(self):
        today = date.today()

        self.add_batch(
            "RECON-1", 10, 2, today + timedelta(days=5)
        )
        self.add_batch(
            "RECON-2", 20, 3, today + timedelta(days=10)
        )

        self.consume(8)

        self.db.refresh(self.inventory)

        batches = (
            self.db.query(ResourceBatch)
            .filter(
                ResourceBatch.inventory_id
                == self.inventory.inventory_id
            )
            .all()
        )

        total_quantity = sum(b.quantity for b in batches)
        total_reserved = sum(b.reserved_quantity for b in batches)

        self.assertEqual(
            self.inventory.current_quantity,
            total_quantity,
        )
        self.assertEqual(
            self.inventory.reserved_quantity,
            total_reserved,
        )
        self.assertEqual(
            self.inventory.usable_quantity,
            total_quantity - total_reserved,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
