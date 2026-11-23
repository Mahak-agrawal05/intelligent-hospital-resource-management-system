import unittest
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from models.entities import (
    Hospital,
    Resource,
    Inventory,
    ResourceBatch,
    Recommendation,
)
from security import get_current_user, require_admin


class RecommendationAPITests(unittest.TestCase):
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
        self.SessionLocal = TestSession

        self.db = self.SessionLocal()
        self.source_hospital = Hospital(
            hospital_name="API Source Hospital",
            location="Test City",
            hospital_type="General",
        )
        self.target_hospital = Hospital(
            hospital_name="API Target Hospital",
            location="Test City",
            hospital_type="General",
        )
        self.resource = Resource(
            resource_name="API Test Medicine",
            category="Medicine",
            unit="Units",
            reorder_level=10,
            safety_stock=5,
            lead_time_days=2,
        )
        self.db.add_all([
            self.source_hospital,
            self.target_hospital,
            self.resource,
        ])
        self.db.flush()

        self.current_user = {
            "user_id": 1,
            "role": "ADMIN",
            "hospital_id": self.target_hospital.hospital_id,
        }

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        def override_current_user():
            return self.current_user

        def override_admin():
            return self.current_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_current_user
        app.dependency_overrides[require_admin] = override_admin

        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def set_user_hospital(self, hospital_id):
        self.current_user = {
            "user_id": 1,
            "role": "ADMIN",
            "hospital_id": hospital_id,
        }

    def make_inventory(self, hospital_id, quantity=0, reserved=0):
        inventory = Inventory(
            hospital_id=hospital_id,
            resource_id=self.resource.resource_id,
            current_quantity=quantity,
            reserved_quantity=reserved,
            usable_quantity=quantity - reserved,
        )
        self.db.add(inventory)
        self.db.flush()
        return inventory

    def make_recommendation(
        self,
        recommendation_type,
        status,
        hospital_id,
        quantity,
        source_id=None,
        target_id=None,
    ):
        recommendation = Recommendation(
            hospital_id=hospital_id,
            resource_id=self.resource.resource_id,
            recommendation_type=recommendation_type,
            recommended_quantity=quantity,
            source_hospital_id=source_id,
            target_hospital_id=target_id,
            reason="API integration test",
            priority="HIGH",
            status=status,
        )
        self.db.add(recommendation)
        self.db.commit()
        self.db.refresh(recommendation)
        return recommendation

    def test_health_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.json())

    def test_source_approval_then_target_executes_redistribution(self):
        source = self.make_inventory(
            self.source_hospital.hospital_id
        )
        source_batch = ResourceBatch(
            inventory_id=source.inventory_id,
            batch_number="API-FEFO-001",
            quantity=10,
            reserved_quantity=0,
            manufacturing_date=date.today() - timedelta(days=30),
            expiry_date=date.today() + timedelta(days=90),
            received_date=date.today() - timedelta(days=20),
        )
        self.db.add(source_batch)
        source.current_quantity = 10
        source.usable_quantity = 10

        recommendation = self.make_recommendation(
            recommendation_type="REDISTRIBUTION",
            status="PENDING",
            hospital_id=self.target_hospital.hospital_id,
            quantity=4,
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
        )

        # Source hospital admin authorizes dispatch.
        self.set_user_hospital(self.source_hospital.hospital_id)
        source_response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/source-approve"
        )
        self.assertEqual(source_response.status_code, 200, source_response.text)
        self.assertEqual(source_response.json()["status"], "SOURCE_APPROVED")

        # Source approval must not move any stock.
        self.db.refresh(source)
        self.db.refresh(source_batch)
        self.assertEqual(source_batch.quantity, 10)
        self.assertEqual(source.current_quantity, 10)

        # Receiving hospital admin performs the second approval/execution.
        self.set_user_hospital(self.target_hospital.hospital_id)
        execute_response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/approve"
        )
        self.assertEqual(execute_response.status_code, 200, execute_response.text)
        self.assertEqual(execute_response.json()["status"], "EXECUTED")

        self.db.refresh(source)
        self.db.refresh(source_batch)
        self.assertEqual(source_batch.quantity, 6)
        self.assertEqual(source.current_quantity, 6)

        target = (
            self.db.query(Inventory)
            .filter(
                Inventory.hospital_id == self.target_hospital.hospital_id,
                Inventory.resource_id == self.resource.resource_id,
            )
            .one()
        )
        self.assertEqual(target.current_quantity, 4)
        self.assertEqual(target.usable_quantity, 4)

        target_batch = (
            self.db.query(ResourceBatch)
            .filter(ResourceBatch.inventory_id == target.inventory_id)
            .one()
        )
        self.assertEqual(target_batch.batch_number, "API-FEFO-001")
        self.assertEqual(target_batch.quantity, 4)

    def test_redistribution_cannot_execute_before_source_approval(self):
        self.make_inventory(self.source_hospital.hospital_id, quantity=8)
        recommendation = self.make_recommendation(
            recommendation_type="REDISTRIBUTION",
            status="PENDING",
            hospital_id=self.target_hospital.hospital_id,
            quantity=3,
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
        )

        self.set_user_hospital(self.target_hospital.hospital_id)
        response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/approve"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Source hospital approval", response.json()["detail"])

    def test_procurement_approval_then_receipt(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="PENDING",
            hospital_id=self.target_hospital.hospital_id,
            quantity=12,
        )
        self.set_user_hospital(self.target_hospital.hospital_id)

        approval_response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/approve"
        )
        self.assertEqual(
            approval_response.status_code, 200, approval_response.text
        )
        self.assertEqual(approval_response.json()["status"], "APPROVED")

        today = date.today()
        receipt_response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/receive",
            json={
                "batch_number": "API-PROC-001",
                "manufacturing_date": (today - timedelta(days=10)).isoformat(),
                "expiry_date": (today + timedelta(days=180)).isoformat(),
                "received_date": today.isoformat(),
            },
        )
        self.assertEqual(
            receipt_response.status_code, 200, receipt_response.text
        )
        self.assertEqual(receipt_response.json()["status"], "RECEIVED")

        self.db.expire_all()
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
        self.assertEqual(inventory.current_quantity, 12)
        self.assertEqual(inventory.usable_quantity, 12)
        self.assertEqual(batch.batch_number, "API-PROC-001")
        self.assertEqual(batch.quantity, 12)

    def test_procurement_receipt_rejected_before_approval(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="PENDING",
            hospital_id=self.target_hospital.hospital_id,
            quantity=7,
        )
        self.set_user_hospital(self.target_hospital.hospital_id)

        response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/receive",
            json={
                "batch_number": "API-NOT-APPROVED",
                "expiry_date": (date.today() + timedelta(days=60)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db.query(Inventory).count(), 0)
        self.assertEqual(self.db.query(ResourceBatch).count(), 0)

    def test_other_hospital_cannot_approve_recommendation(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="PENDING",
            hospital_id=self.target_hospital.hospital_id,
            quantity=5,
        )
        self.set_user_hospital(self.source_hospital.hospital_id)

        response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/approve"
        )
        self.assertEqual(response.status_code, 404)


    def test_procurement_recommendation_cannot_be_approved_twice(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="PENDING",
            hospital_id=self.target_hospital.hospital_id,
            quantity=5,
        )
        self.set_user_hospital(self.target_hospital.hospital_id)
        endpoint = f"/recommendations/{recommendation.recommendation_id}/approve"

        first = self.client.post(endpoint)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["status"], "APPROVED")

        second = self.client.post(endpoint)
        self.assertEqual(second.status_code, 400, second.text)

        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "APPROVED")

    def test_redistribution_cannot_be_executed_twice_through_api(self):
        source = self.make_inventory(
            self.source_hospital.hospital_id, quantity=10
        )
        target = self.make_inventory(
            self.target_hospital.hospital_id, quantity=0
        )
        recommendation = self.make_recommendation(
            recommendation_type="REDISTRIBUTION",
            status="SOURCE_APPROVED",
            hospital_id=self.target_hospital.hospital_id,
            quantity=4,
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
        )
        self.set_user_hospital(self.target_hospital.hospital_id)
        endpoint = f"/recommendations/{recommendation.recommendation_id}/approve"

        first = self.client.post(endpoint)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["status"], "EXECUTED")

        second = self.client.post(endpoint)
        self.assertEqual(second.status_code, 400, second.text)

        self.db.refresh(source)
        self.db.refresh(target)
        self.db.refresh(recommendation)
        self.assertEqual(source.current_quantity, 6)
        self.assertEqual(target.current_quantity, 4)
        self.assertEqual(recommendation.status, "EXECUTED")

    def test_unrelated_hospital_cannot_source_approve_redistribution(self):
        recommendation = self.make_recommendation(
            recommendation_type="REDISTRIBUTION",
            status="PENDING",
            hospital_id=self.target_hospital.hospital_id,
            quantity=3,
            source_id=self.source_hospital.hospital_id,
            target_id=self.target_hospital.hospital_id,
        )
        self.set_user_hospital(999999)

        response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/source-approve"
        )
        self.assertEqual(response.status_code, 404, response.text)

        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "PENDING")

    def test_expired_procurement_receipt_rejected_through_api(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="APPROVED",
            hospital_id=self.target_hospital.hospital_id,
            quantity=8,
        )
        self.set_user_hospital(self.target_hospital.hospital_id)

        response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/receive",
            json={
                "batch_number": "API-EXPIRED-001",
                "manufacturing_date": (date.today() - timedelta(days=60)).isoformat(),
                "expiry_date": (date.today() - timedelta(days=1)).isoformat(),
                "received_date": date.today().isoformat(),
            },
        )

        self.assertEqual(response.status_code, 400, response.text)
        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "APPROVED")
        self.assertEqual(self.db.query(Inventory).count(), 0)
        self.assertEqual(self.db.query(ResourceBatch).count(), 0)

    def test_procurement_receipt_cannot_be_submitted_twice_through_api(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="APPROVED",
            hospital_id=self.target_hospital.hospital_id,
            quantity=6,
        )
        self.set_user_hospital(self.target_hospital.hospital_id)
        endpoint = f"/recommendations/{recommendation.recommendation_id}/receive"
        today = date.today()
        payload = {
            "batch_number": "API-RECEIPT-ONCE",
            "manufacturing_date": (today - timedelta(days=10)).isoformat(),
            "expiry_date": (today + timedelta(days=90)).isoformat(),
            "received_date": today.isoformat(),
        }

        first = self.client.post(endpoint, json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["status"], "RECEIVED")

        second_payload = {
            **payload,
            "batch_number": "API-RECEIPT-TWICE",
        }
        second = self.client.post(endpoint, json=second_payload)
        self.assertEqual(second.status_code, 400, second.text)

        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "RECEIVED")
        self.assertEqual(self.db.query(ResourceBatch).count(), 1)
        inventory = self.db.query(Inventory).one()
        self.assertEqual(inventory.current_quantity, 6)


    def test_pending_recommendation_can_be_rejected_with_reason(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="PENDING",
            hospital_id=self.target_hospital.hospital_id,
            quantity=5,
        )
        self.set_user_hospital(self.target_hospital.hospital_id)

        response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/reject",
            json={"rejection_reason": "Current stock is sufficient."},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "REJECTED")
        self.assertEqual(
            response.json()["rejection_reason"],
            "Current stock is sufficient.",
        )

        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "REJECTED")
        self.assertEqual(
            recommendation.rejection_reason,
            "Current stock is sufficient.",
        )

    def test_rejection_reason_cannot_be_blank(self):
        recommendation = self.make_recommendation(
            recommendation_type="MAINTENANCE",
            status="PENDING",
            hospital_id=self.target_hospital.hospital_id,
            quantity=1,
        )
        self.set_user_hospital(self.target_hospital.hospital_id)

        response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/reject",
            json={"rejection_reason": "   "},
        )

        self.assertEqual(response.status_code, 422, response.text)
        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "PENDING")
        self.assertIsNone(recommendation.rejection_reason)

    def test_other_hospital_cannot_reject_recommendation(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="PENDING",
            hospital_id=self.target_hospital.hospital_id,
            quantity=5,
        )
        self.set_user_hospital(self.source_hospital.hospital_id)

        response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/reject",
            json={"rejection_reason": "Not my hospital's recommendation."},
        )

        self.assertEqual(response.status_code, 404, response.text)
        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "PENDING")
        self.assertIsNone(recommendation.rejection_reason)

    def test_recommendation_cannot_be_rejected_twice(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="PENDING",
            hospital_id=self.target_hospital.hospital_id,
            quantity=5,
        )
        self.set_user_hospital(self.target_hospital.hospital_id)
        endpoint = f"/recommendations/{recommendation.recommendation_id}/reject"

        first = self.client.post(
            endpoint,
            json={"rejection_reason": "Duplicate stock already available."},
        )
        self.assertEqual(first.status_code, 200, first.text)

        second = self.client.post(
            endpoint,
            json={"rejection_reason": "Trying to reject again."},
        )
        self.assertEqual(second.status_code, 400, second.text)

        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "REJECTED")
        self.assertEqual(
            recommendation.rejection_reason,
            "Duplicate stock already available.",
        )

    def test_rejected_recommendation_cannot_be_approved(self):
        recommendation = self.make_recommendation(
            recommendation_type="PROCUREMENT",
            status="REJECTED",
            hospital_id=self.target_hospital.hospital_id,
            quantity=5,
        )
        recommendation.rejection_reason = "Procurement is not required."
        self.db.commit()
        self.set_user_hospital(self.target_hospital.hospital_id)

        response = self.client.post(
            f"/recommendations/{recommendation.recommendation_id}/approve"
        )

        self.assertEqual(response.status_code, 400, response.text)
        self.db.refresh(recommendation)
        self.assertEqual(recommendation.status, "REJECTED")
        self.assertEqual(
            recommendation.rejection_reason,
            "Procurement is not required.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
