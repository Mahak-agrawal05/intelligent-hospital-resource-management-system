from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Numeric,
    Text,
    Float,
    ForeignKey
)

from datetime import datetime

from database import Base


# =========================================================
# 1. HOSPITAL
# =========================================================

class Hospital(Base):

    __tablename__ = "hospitals"

    hospital_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    hospital_name = Column(
        String,
        nullable=False
    )

    location = Column(
        String,
        nullable=False
    )

    hospital_type = Column(
        String,
        nullable=False
    )


# =========================================================
# 2. USER
# =========================================================

class User(Base):

    __tablename__ = "users"

    user_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String,
        nullable=True
    )

    email = Column(
        String,
        nullable=True,
        unique=True
    )

    password_hash = Column(
        String,
        nullable=True
    )

    role = Column(
        String,
        nullable=True
    )

    hospital_id = Column(
        Integer,
        ForeignKey("hospitals.hospital_id"),
        nullable=False
    )


# =========================================================
# 3. RESOURCE
# =========================================================

class Resource(Base):

    __tablename__ = "resources"

    resource_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    resource_name = Column(
        String,
        nullable=False
    )

    category = Column(
        String,
        nullable=False
    )

    unit = Column(
        String,
        nullable=False
    )

    supplier_id = Column(
        Integer,
        ForeignKey("suppliers.supplier_id"),
        nullable=True
    )

    reorder_level = Column(
        Integer,
        nullable=False
    )

    safety_stock = Column(
        Integer,
        nullable=False
    )

    lead_time_days = Column(
        Integer,
        nullable=False
    )


# =========================================================
# 4. INVENTORY
# =========================================================

class Inventory(Base):

    __tablename__ = "inventory"

    inventory_id = Column(
    Integer,
    primary_key=True,
    autoincrement=True,
    index=True
)

    hospital_id = Column(
        Integer,
        ForeignKey("hospitals.hospital_id"),
        nullable=False
    )

    resource_id = Column(
        Integer,
        ForeignKey("resources.resource_id"),
        nullable=False
    )

    current_quantity = Column(
        Integer,
        nullable=False
    )

    reserved_quantity = Column(
        Integer,
        nullable=False
    )

    usable_quantity = Column(
        Integer,
        nullable=False
    )

    last_updated = Column(
        DateTime(timezone=True),
        nullable=True
    )


# =========================================================
# 5. RESOURCE BATCH
# =========================================================

class ResourceBatch(Base):

    __tablename__ = "resource_batches"

    batch_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    inventory_id = Column(
        Integer,
        ForeignKey("inventory.inventory_id"),
        nullable=False
    )

    batch_number = Column(
        String,
        nullable=False
    )

    quantity = Column(
        Integer,
        nullable=False
    )

    manufacturing_date = Column(
        Date,
        nullable=True
    )

    expiry_date = Column(
        Date,
        nullable=False
    )

    received_date = Column(
        Date,
        nullable=True
    )


# =========================================================
# 6. CONSUMPTION HISTORY
# =========================================================

class ConsumptionHistory(Base):

    __tablename__ = "consumption_history"

    consumption_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    hospital_id = Column(
        Integer,
        ForeignKey("hospitals.hospital_id"),
        nullable=False
    )

    resource_id = Column(
        Integer,
        ForeignKey("resources.resource_id"),
        nullable=False
    )

    consumption_date = Column(
        Date,
        nullable=False
    )

    quantity_consumed = Column(
        Integer,
        nullable=False
    )


# =========================================================
# 7. SUPPLIER
# =========================================================

class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id = Column(Integer, primary_key=True, index=True)
    supplier_name = Column(String, nullable=False)
    contact_info = Column(String, nullable=True)
    average_lead_time = Column(Integer, nullable=False)
    reliability_score = Column(Float, nullable=True)

    procurement_cost_per_unit = Column(Float, default=0)

# =========================================================
# 8. EQUIPMENT
# =========================================================

class Equipment(Base):
    __tablename__ = "equipment"

    equipment_id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.hospital_id"), nullable=False)
    equipment_name = Column(String, nullable=False)
    equipment_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    manufacturer = Column(String, nullable=True)
    model_number = Column(String, nullable=True)
    installation_date = Column(Date, nullable=True)

    utilization_hours = Column(Float, default=0)
    available_hours = Column(Float, default=0)

# =========================================================
# 9. MAINTENANCE RECORD
# =========================================================

class MaintenanceRecord(Base):

    __tablename__ = "maintenance_records"

    maintenance_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    equipment_id = Column(
        Integer,
        ForeignKey("equipment.equipment_id"),
        nullable=False
    )

    maintenance_date = Column(
        Date,
        nullable=False
    )

    maintenance_type = Column(
        String,
        nullable=False
    )

    downtime_hours = Column(
        Numeric,
        nullable=True
    )

    maintenance_cost = Column(
        Numeric,
        nullable=True
    )

    failure_reason = Column(
        String,
        nullable=True
    )

    notes = Column(
        Text,
        nullable=True
    )

class DemandPrediction(Base):
    __tablename__ = "demand_predictions"

    prediction_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    hospital_id = Column(
        Integer,
        ForeignKey("hospitals.hospital_id"),
        nullable=False
    )

    resource_id = Column(
        Integer,
        ForeignKey("resources.resource_id"),
        nullable=False
    )

    prediction_date = Column(
        Date,
        nullable=False
    )

    forecast_date = Column(
        Date,
        nullable=False
    )

    predicted_quantity = Column(
        Float,
        nullable=False
    )

    model_name = Column(
        String,
        nullable=False
    )


class RiskAnalysis(Base):
    __tablename__ = "risk_analysis"

    risk_id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(
        Integer,
        ForeignKey("hospitals.hospital_id"),
        nullable=False
    )
    resource_id = Column(
        Integer,
        ForeignKey("resources.resource_id"),
        nullable=False
    )

    analysis_date = Column(Date, nullable=False)

    shortage_risk = Column(Float, nullable=False)
    wastage_risk = Column(Float, nullable=False)

    risk_level = Column(String, nullable=False)

    expected_stockout_date = Column(Date, nullable=True)
    expected_wastage_quantity = Column(Float, nullable=True)

class Recommendation(Base):
    __tablename__ = "recommendations"

    recommendation_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    hospital_id = Column(
        Integer,
        ForeignKey("hospitals.hospital_id"),
        nullable=False
    )

    resource_id = Column(
        Integer,
        ForeignKey("resources.resource_id"),
        nullable=False
    )

    recommendation_type = Column(
        String,
        nullable=False
    )

    recommended_quantity = Column(
        Float,
        nullable=False
    )

    source_hospital_id = Column(
        Integer,
        ForeignKey("hospitals.hospital_id"),
        nullable=True
    )

    target_hospital_id = Column(
        Integer,
        ForeignKey("hospitals.hospital_id"),
        nullable=True
    )

    reason = Column(
        String,
        nullable=True
    )

    status = Column(
        String,
        nullable=False,
        default="PENDING"
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )