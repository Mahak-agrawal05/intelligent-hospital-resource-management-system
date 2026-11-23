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
    Recommendation,
)
from services.entity_service import (
    approve_source_redistribution,
    execute_approved_redistribution,
    receive_procurement,
)


class RecommendationWorkflowTests(unittest.TestCase):
    def setUp(self):
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

        self.source_hospital = Hospital(
            hospital_name="Source Hospital",
            location="Test City",
            hospital_type="General",
        )
        self.target_hospital = Hospital(
            hospital_name="Target Hospital",
            location="Test City",
            hospital_type="General",
        )
        self.other_hospital = Hospital(
            hospital_name="Other Hospital",
            location="Test City",
            hospital_type="General",
        )
        self.resource = Resource(
            resource_name="Test Medicine",
            category="Medicine",
            unit="Units",
            reorder_level=10,
            safety_stock=5,
            lead_time_days=2,
        )
        self.db.add_all([
            self.source_hospital,
            self.target_hospital,
            self.other_hospital,
            self.resource,
        ])
        self.db.flush()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def make_inventory(self, hospital_id, current=0, reserved=0, usable=None):
        if usable is None:
            usable = current - reserved
        inventory = Inventory(
            hospital_id=hospital_id,
            resource_id=self.resource.resource_id,
            current_quantity=current,
            reserved_quantity=reserved,
            usable_quantity=usable,
        )
        self.db.add(inventory)
        self.db.flush()
        return inventory

    def make_batch(
        self,
        inventory,
        number,
        quantity,
        expiry,
        reserved=0,
        manufacturing_date=None,
    ):
        batch = ResourceBatch(
            inventory_id=inventory.inventory_id,
            batch_number=number,
            quantity=quantity,
            reserved_quantity=reserved,
            manufacturing_date=manufacturing_date,
            expiry_date=expiry,
            received_date=date.today() - timedelta(days=1),
        )
        self.db.add(batch)
        self.db.flush()
        return batch

    def make_recommendation(
        self,
        recommendation_type="REDISTRIBUTION",
        status="PENDING",
        hospital_id=None,
        source_id=None,
        target_id=None,
        quantity=5.0,
    ):
        recommendation = Recommendation(
            hospital_id=(
                hospital_id
                if hospital_id is not None
                else self.target_hospital.hospital_id
            ),
            resource_id=self.resource.resource_id,
            recommendation_type=recommendation_type,
            recommended_quantity=quantity,
            source_hospital_id=source_id,
            target_hospital_id=target_id,
            reason="Automated test recommendation",
            priority="HIGH",
            status=status,
        )
        self.db.add(recommendation)
        self.db.flush()
        return recommendation

    def test_source_approval_changes_status_without_moving_stock(self):
        source = self.make_inventory(
            self.source_hospital.hospital_id, current=10
        )
        target = self.make_inventory(
            self.target_hospital.hospital_id, current=2
        )
        recommendation = self.make_recommendation(
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
            quantity=5,
        )
        self.db.commit()

        approved = approve_source_redistribution(
            self.db,
            recommendation.recommendation_id,
            self.source_hospital.hospital_id,
        )

        self.db.refresh(source)
        self.db.refresh(target)
        self.assertEqual(approved.status, "SOURCE_APPROVED")
        self.assertEqual(source.current_quantity, 10)
        self.assertEqual(target.current_quantity, 2)

    def test_only_source_hospital_can_approve(self):
        recommendation = self.make_recommendation(
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            approve_source_redistribution(
                self.db,
                recommendation.recommendation_id,
                self.other_hospital.hospital_id,
            )

        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "PENDING")

    def test_non_redistribution_cannot_be_source_approved(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            approve_source_redistribution(
                self.db,
                recommendation.recommendation_id,
                self.source_hospital.hospital_id,
            )

        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "PENDING")

    def test_batch_redistribution_uses_fefo_and_reconciles_both_hospitals(self):
        today = date.today()
        source = self.make_inventory(
            self.source_hospital.hospital_id
        )
        early = self.make_batch(
            source,
            "EARLY-EXPIRY",
            4,
            today + timedelta(days=5),
            manufacturing_date=today - timedelta(days=100),
        )
        later = self.make_batch(
            source,
            "LATER-EXPIRY",
            10,
            today + timedelta(days=20),
            manufacturing_date=today - timedelta(days=80),
        )
        # Reconcile source aggregate values to its batch ledger.
        source.current_quantity = 14
        source.reserved_quantity = 0
        source.usable_quantity = 14

        recommendation = self.make_recommendation(
            status="SOURCE_APPROVED",
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
            quantity=6,
        )
        self.db.commit()

        result = execute_approved_redistribution(
            self.db, recommendation
        )

        self.db.refresh(source)
        self.db.refresh(early)
        self.db.refresh(later)

        target = (
            self.db.query(Inventory)
            .filter(
                Inventory.hospital_id == self.target_hospital.hospital_id,
                Inventory.resource_id == self.resource.resource_id,
            )
            .one()
        )
        target_batches = (
            self.db.query(ResourceBatch)
            .filter(ResourceBatch.inventory_id == target.inventory_id)
            .order_by(ResourceBatch.expiry_date, ResourceBatch.batch_id)
            .all()
        )

        self.assertEqual(result["quantity_transferred"], 6)
        self.assertEqual(recommendation.status, "EXECUTED")
        self.assertEqual(early.quantity, 0)
        self.assertEqual(later.quantity, 8)
        self.assertEqual(source.current_quantity, 8)
        self.assertEqual(source.usable_quantity, 8)
        self.assertEqual(target.current_quantity, 6)
        self.assertEqual(target.usable_quantity, 6)
        self.assertEqual(len(target_batches), 2)
        self.assertEqual(
            [(b.batch_number, b.quantity) for b in target_batches],
            [("EARLY-EXPIRY", 4), ("LATER-EXPIRY", 2)],
        )
        self.assertEqual(
            target_batches[0].manufacturing_date,
            early.manufacturing_date,
        )
        self.assertEqual(
            target_batches[0].expiry_date,
            early.expiry_date,
        )

    def test_redistribution_requires_source_approval(self):
        self.make_inventory(
            self.source_hospital.hospital_id, current=10
        )
        recommendation = self.make_recommendation(
            status="PENDING",
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
            quantity=3,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            execute_approved_redistribution(self.db, recommendation)

        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "PENDING")

    def test_batch_transfer_rejects_aggregate_only_target_without_mutation(self):
        source = self.make_inventory(self.source_hospital.hospital_id)
        self.make_batch(
            source, "SOURCE-BATCH", 10, date.today() + timedelta(days=10)
        )
        source.current_quantity = 10
        source.usable_quantity = 10

        target = self.make_inventory(
            self.target_hospital.hospital_id, current=2
        )
        recommendation = self.make_recommendation(
            status="SOURCE_APPROVED",
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
            quantity=3,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            execute_approved_redistribution(self.db, recommendation)

        self.db.refresh(source)
        self.db.refresh(target)
        self.db.refresh(recommendation)
        source_batch = (
            self.db.query(ResourceBatch)
            .filter(ResourceBatch.inventory_id == source.inventory_id)
            .one()
        )
        self.assertEqual(source_batch.quantity, 10)
        self.assertEqual(source.current_quantity, 10)
        self.assertEqual(target.current_quantity, 2)
        self.assertEqual(recommendation.status, "SOURCE_APPROVED")

    def test_aggregate_only_redistribution(self):
        source = self.make_inventory(
            self.source_hospital.hospital_id, current=12, reserved=2
        )
        target = self.make_inventory(
            self.target_hospital.hospital_id, current=3, reserved=1
        )
        recommendation = self.make_recommendation(
            status="SOURCE_APPROVED",
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
            quantity=5,
        )
        self.db.commit()

        execute_approved_redistribution(self.db, recommendation)

        self.db.refresh(source)
        self.db.refresh(target)
        self.assertEqual(source.current_quantity, 7)
        self.assertEqual(source.reserved_quantity, 2)
        self.assertEqual(source.usable_quantity, 5)
        self.assertEqual(target.current_quantity, 8)
        self.assertEqual(target.reserved_quantity, 1)
        self.assertEqual(target.usable_quantity, 7)
        self.assertEqual(recommendation.status, "EXECUTED")

    def test_aggregate_only_stock_cannot_move_into_batch_target(self):
        source = self.make_inventory(
            self.source_hospital.hospital_id, current=10
        )
        target = self.make_inventory(self.target_hospital.hospital_id)
        self.make_batch(
            target, "TARGET-BATCH", 2, date.today() + timedelta(days=10)
        )
        target.current_quantity = 2
        target.usable_quantity = 2

        recommendation = self.make_recommendation(
            status="SOURCE_APPROVED",
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
            quantity=3,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            execute_approved_redistribution(self.db, recommendation)

        self.db.refresh(source)
        self.db.refresh(target)
        self.assertEqual(source.current_quantity, 10)
        self.assertEqual(target.current_quantity, 2)
        self.assertEqual(recommendation.status, "SOURCE_APPROVED")

    def test_procurement_receipt_creates_batch_and_reconciles_inventory(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="APPROVED",
            hospital_id=self.target_hospital.hospital_id,
            quantity=25,
        )
        self.db.commit()

        today = date.today()
        result = receive_procurement(
            db=self.db,
            recommendation_id=recommendation.recommendation_id,
            hospital_id=self.target_hospital.hospital_id,
            batch_number="PROC-001",
            manufacturing_date=today - timedelta(days=30),
            expiry_date=today + timedelta(days=365),
            received_date=today,
        )

        self.db.refresh(recommendation)
        inventory = (
            self.db.query(Inventory)
            .filter(
                Inventory.hospital_id == self.target_hospital.hospital_id,
                Inventory.resource_id == self.resource.resource_id,
            )
            .one()
        )
        batch = (
            self.db.query(ResourceBatch)
            .filter(ResourceBatch.inventory_id == inventory.inventory_id)
            .one()
        )

        self.assertEqual(result["quantity_received"], 25)
        self.assertEqual(recommendation.status, "RECEIVED")
        self.assertEqual(batch.batch_number, "PROC-001")
        self.assertEqual(batch.quantity, 25)
        self.assertEqual(batch.manufacturing_date, today - timedelta(days=30))
        self.assertEqual(batch.expiry_date, today + timedelta(days=365))
        self.assertEqual(inventory.current_quantity, 25)
        self.assertEqual(inventory.reserved_quantity, 0)
        self.assertEqual(inventory.usable_quantity, 25)

    def test_procurement_rejects_wrong_hospital(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="APPROVED",
            hospital_id=self.target_hospital.hospital_id,
            quantity=10,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            receive_procurement(
                self.db,
                recommendation.recommendation_id,
                self.other_hospital.hospital_id,
                "WRONG-HOSPITAL",
                date.today() + timedelta(days=30),
            )

        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "APPROVED")
        self.assertEqual(self.db.query(ResourceBatch).count(), 0)

    def test_procurement_rejects_expired_batch_without_partial_changes(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="APPROVED",
            hospital_id=self.target_hospital.hospital_id,
            quantity=10,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            receive_procurement(
                self.db,
                recommendation.recommendation_id,
                self.target_hospital.hospital_id,
                "EXPIRED-BATCH",
                date.today() - timedelta(days=1),
            )

        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "APPROVED")
        self.assertEqual(self.db.query(Inventory).count(), 0)
        self.assertEqual(self.db.query(ResourceBatch).count(), 0)

    def test_procurement_rejects_aggregate_only_inventory(self):
        inventory = self.make_inventory(
            self.target_hospital.hospital_id, current=4
        )
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="APPROVED",
            hospital_id=self.target_hospital.hospital_id,
            quantity=10,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            receive_procurement(
                self.db,
                recommendation.recommendation_id,
                self.target_hospital.hospital_id,
                "PROC-AGGREGATE",
                date.today() + timedelta(days=30),
            )

        self.db.refresh(inventory)
        self.db.refresh(recommendation)
        self.assertEqual(inventory.current_quantity, 4)
        self.assertEqual(recommendation.status, "APPROVED")
        self.assertEqual(self.db.query(ResourceBatch).count(), 0)

    def test_procurement_cannot_be_received_twice(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="APPROVED",
            hospital_id=self.target_hospital.hospital_id,
            quantity=10,
        )
        self.db.commit()

        receive_procurement(
            self.db,
            recommendation.recommendation_id,
            self.target_hospital.hospital_id,
            "PROC-ONCE",
            date.today() + timedelta(days=30),
        )

        with self.assertRaises(ValueError):
            receive_procurement(
                self.db,
                recommendation.recommendation_id,
                self.target_hospital.hospital_id,
                "PROC-TWICE",
                date.today() + timedelta(days=40),
            )

        self.assertEqual(self.db.query(ResourceBatch).count(), 1)
        inventory = self.db.query(Inventory).one()
        self.assertEqual(inventory.current_quantity, 10)

    def test_procurement_requires_approved_status(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="PENDING",
            hospital_id=self.target_hospital.hospital_id,
            quantity=10,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            receive_procurement(
                self.db,
                recommendation.recommendation_id,
                self.target_hospital.hospital_id,
                "NOT-APPROVED",
                date.today() + timedelta(days=30),
            )

        self.assertEqual(self.db.query(Inventory).count(), 0)
        self.assertEqual(self.db.query(ResourceBatch).count(), 0)


    def test_redistribution_cannot_be_executed_twice(self):
        source = self.make_inventory(
            self.source_hospital.hospital_id, current=10
        )
        target = self.make_inventory(
            self.target_hospital.hospital_id, current=0
        )
        recommendation = self.make_recommendation(
            status="SOURCE_APPROVED",
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
            quantity=4,
        )
        self.db.commit()

        execute_approved_redistribution(self.db, recommendation)

        with self.assertRaises(ValueError):
            execute_approved_redistribution(self.db, recommendation)

        self.db.refresh(source)
        self.db.refresh(target)
        self.db.refresh(recommendation)
        self.assertEqual(source.current_quantity, 6)
        self.assertEqual(target.current_quantity, 4)
        self.assertEqual(recommendation.status, "EXECUTED")

    def test_redistribution_rejects_insufficient_source_stock_without_mutation(self):
        source = self.make_inventory(
            self.source_hospital.hospital_id, current=3, reserved=1
        )
        target = self.make_inventory(
            self.target_hospital.hospital_id, current=2
        )
        recommendation = self.make_recommendation(
            status="SOURCE_APPROVED",
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
            quantity=3,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            execute_approved_redistribution(self.db, recommendation)

        self.db.refresh(source)
        self.db.refresh(target)
        self.db.refresh(recommendation)
        self.assertEqual(source.current_quantity, 3)
        self.assertEqual(source.reserved_quantity, 1)
        self.assertEqual(source.usable_quantity, 2)
        self.assertEqual(target.current_quantity, 2)
        self.assertEqual(recommendation.status, "SOURCE_APPROVED")

    def test_redistribution_rejects_zero_quantity_without_mutation(self):
        source = self.make_inventory(
            self.source_hospital.hospital_id, current=10
        )
        target = self.make_inventory(
            self.target_hospital.hospital_id, current=0
        )
        recommendation = self.make_recommendation(
            status="SOURCE_APPROVED",
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
            quantity=0,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            execute_approved_redistribution(self.db, recommendation)

        self.db.refresh(source)
        self.db.refresh(target)
        self.db.refresh(recommendation)
        self.assertEqual(source.current_quantity, 10)
        self.assertEqual(target.current_quantity, 0)
        self.assertEqual(recommendation.status, "SOURCE_APPROVED")

    def test_redistribution_rejects_negative_quantity_without_mutation(self):
        source = self.make_inventory(
            self.source_hospital.hospital_id, current=10
        )
        target = self.make_inventory(
            self.target_hospital.hospital_id, current=0
        )
        recommendation = self.make_recommendation(
            status="SOURCE_APPROVED",
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
            quantity=-2,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            execute_approved_redistribution(self.db, recommendation)

        self.db.refresh(source)
        self.db.refresh(target)
        self.db.refresh(recommendation)
        self.assertEqual(source.current_quantity, 10)
        self.assertEqual(target.current_quantity, 0)
        self.assertEqual(recommendation.status, "SOURCE_APPROVED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
