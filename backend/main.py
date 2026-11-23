from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field

from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy.orm import Session

from sqlalchemy import text
from sqlalchemy import func

from fastapi.middleware.cors import CORSMiddleware

from datetime import date, timedelta


from database import get_db


from models.entities import (
    User,
    Inventory,
    Resource,
    ResourceBatch,
    DemandPrediction,
    RiskAnalysis,
    Equipment,
    MaintenanceRecord,
    Supplier,
    Recommendation,
    ConsumptionHistory
)


from risk.shortage_risk import calculate_shortage_risk

from risk.wastage_risk import calculate_wastage_risk


from schemas.entities import (
    HospitalCreate,
    UserCreate,
    ResourceCreate,
    InventoryCreate,
    ResourceBatchCreate,
    ConsumptionHistoryCreate,
    SupplierCreate,
    EquipmentCreate,
    MaintenanceRecordCreate,
    ProcurementReceiptCreate,
)


from services.entity_service import (
    get_all_hospitals,
    create_hospital,
    get_all_users,
    create_user,
    get_all_resources,
    create_resource,
    get_all_inventory,
    create_inventory,
    get_all_batches,
    create_batch,
    get_all_consumption,
    create_consumption,
    get_all_suppliers,
    create_supplier,
    get_all_equipment,
    create_equipment,
    get_all_maintenance_records,
    create_maintenance_record,
    create_risk_analysis,
    optimize_resource_allocation,
    get_all_risk_analysis,
    approve_source_redistribution,
    execute_approved_redistribution,
    receive_procurement,
)


from services.recommendation_priority import calculate_recommendation_priority


from security import (
    verify_password,
    create_access_token,
    get_current_user,
    require_admin,
    require_central_admin,
    hash_password
)

app = FastAPI(
    title="Intelligent Hospital Resource Allocation System",
    description="Backend API for hospital resource and inventory management",
    version="1.0.0",
)

import os

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================

# HOME

# =========================================================


@app.get("/")
def home():

    return {"message": "Intelligent Hospital Resource System API is running"}


# =========================================================

# HOSPITALS

# =========================================================


@app.get("/hospitals")
def get_hospitals(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return get_all_hospitals(db)


@app.post("/hospitals")
def add_hospital(
    hospital: HospitalCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_central_admin)
):
    return create_hospital(
        db,
        hospital.hospital_name,
        hospital.location,
        hospital.hospital_type
    )


# =========================================================

# USERS

# =========================================================

class UserStatusUpdate(BaseModel):
    is_active: bool

@app.get("/users")
def get_users(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    hospital_id = current_user["hospital_id"]

    users = db.query(User).filter(
        User.hospital_id == hospital_id
    ).all()

    return [
        {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "hospital_id": user.hospital_id,
            "is_active": user.is_active
        }
        for user in users
    ]


@app.post("/users")
def add_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    hashed_password = hash_password(user.password)

    new_user = create_user(
        db,
        user.name,
        user.email,
        hashed_password,
        "staff",
        current_user["hospital_id"]
    )

    return {
        "message": "Staff account created successfully",
        "user_id": new_user.user_id,
        "name": new_user.name,
        "email": new_user.email,
        "role": new_user.role,
        "hospital_id": new_user.hospital_id,
        "is_active": new_user.is_active
    }

@app.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    # Prevent an admin from changing their own account status.
    if user_id == current_user["user_id"]:
        raise HTTPException(
            status_code=400,
            detail="You cannot change your own account status."
        )

    # Find staff belonging to the admin's hospital only.
    user = db.query(User).filter(
        User.user_id == user_id,
        User.hospital_id == current_user["hospital_id"],
        User.role == "staff"
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Staff user not found in your hospital."
        )

    user.is_active = payload.is_active

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return {
        "message": (
            "Staff account activated successfully"
            if user.is_active
            else "Staff account deactivated successfully"
        ),
        "user_id": user.user_id,
        "is_active": user.is_active
    }

# =========================================================

# RESOURCES

# =========================================================


@app.get("/resources")
def get_resources(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return get_all_resources(db)


@app.post("/resources")
def add_resource(
    resource: ResourceCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_central_admin)
):
    return create_resource(
        db,
        resource.resource_name,
        resource.category,
        resource.unit,
        resource.supplier_id,
        resource.reorder_level,
        resource.safety_stock,
        resource.lead_time_days,
        resource.criticality
    )


# =========================================================

# INVENTORY

# =========================================================


@app.get("/inventory")
def get_inventory(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):

    hospital_id = current_user["hospital_id"]

    return get_all_inventory(db, hospital_id)


@app.post("/inventory")
def add_inventory(
    inventory: InventoryCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    if inventory.reserved_quantity > inventory.current_quantity:
        raise HTTPException(
            status_code=400,
            detail="Reserved quantity cannot exceed current quantity."
        )

    hospital_id = current_user["hospital_id"]

    existing_inventory = db.query(Inventory).filter(
        Inventory.hospital_id == hospital_id,
        Inventory.resource_id == inventory.resource_id
    ).first()

    if existing_inventory:
        raise HTTPException(
            status_code=409,
            detail="Inventory already exists for this resource."
        )

    return create_inventory(
        db,
        hospital_id,
        inventory.resource_id,
        inventory.current_quantity,
        inventory.reserved_quantity
    )


# =========================================================

# RESOURCE BATCHES

# =========================================================


@app.get("/resource-batches")
def get_resource_batches(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user["hospital_id"]

    batches = (
        db.query(ResourceBatch)
        .join(
            Inventory,
            ResourceBatch.inventory_id == Inventory.inventory_id
        )
        .filter(Inventory.hospital_id == hospital_id)
        .all()
    )

    return [
        {
            "batch_id": batch.batch_id,
            "inventory_id": batch.inventory_id,
            "batch_number": batch.batch_number,
            "quantity": batch.quantity,
            "reserved_quantity": batch.reserved_quantity,
            "manufacturing_date": (
                batch.manufacturing_date.isoformat()
                if batch.manufacturing_date else None
            ),
            "expiry_date": (
                batch.expiry_date.isoformat()
                if batch.expiry_date else None
            ),
            "received_date": (
                batch.received_date.isoformat()
                if batch.received_date else None
            )
        }
        for batch in batches
    ]


@app.post("/resource-batches")
def add_resource_batch(
    batch: ResourceBatchCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    hospital_id = current_user["hospital_id"]

    inventory = db.query(Inventory).filter(
        Inventory.inventory_id == batch.inventory_id,
        Inventory.hospital_id == hospital_id
    ).first()

    if not inventory:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found for your hospital"
        )

    return create_batch(
        db=db,
        inventory_id=inventory.inventory_id,
        batch_number=batch.batch_number,
        quantity=batch.quantity,
        manufacturing_date=batch.manufacturing_date,
        expiry_date=batch.expiry_date,
        received_date=batch.received_date,
        reserved_quantity=batch.reserved_quantity
    )


# =========================================================

# CONSUMPTION HISTORY

# =========================================================


@app.get("/consumption-history")
def get_consumption_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return db.query(ConsumptionHistory).filter(
        ConsumptionHistory.hospital_id == current_user["hospital_id"]
    ).all()


@app.post("/consumption-history")
def add_consumption_history(
    consumption: ConsumptionHistoryCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user["hospital_id"]

    inventory = db.query(Inventory).filter(
        Inventory.hospital_id == hospital_id,
        Inventory.resource_id == consumption.resource_id
    ).first()

    if not inventory:
        raise HTTPException(
            status_code=404,
            detail="Resource inventory not found for your hospital"
        )

    return create_consumption(
        db,
        hospital_id,
        consumption.resource_id,
        consumption.consumption_date,
        consumption.quantity_consumed
    )


# =========================================================

# SUPPLIERS

# =========================================================


@app.get("/suppliers")
def get_suppliers(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return get_all_suppliers(db)


@app.post("/suppliers")
def add_supplier(
    supplier: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_central_admin)
):
    return create_supplier(
        db,
        supplier.supplier_name,
        supplier.contact_info,
        supplier.average_lead_time,
        supplier.reliability_score
    )


# =========================================================

# EQUIPMENT

# =========================================================


@app.get("/equipment")
def get_equipment(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    return db.query(Equipment).filter(
        Equipment.hospital_id == current_user["hospital_id"]
    ).all()


@app.post("/equipment")
def add_equipment(
    equipment: EquipmentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    return create_equipment(
        db,
        current_user["hospital_id"],
        equipment.equipment_name,
        equipment.equipment_type,
        equipment.manufacturer,
        equipment.model_number,
        equipment.installation_date,
        equipment.status,
        equipment.criticality
    )


# =========================================================

# MAINTENANCE RECORDS

# =========================================================


@app.get("/maintenance-records")
def get_maintenance_records(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    return (
        db.query(MaintenanceRecord)
        .join(
            Equipment,
            Equipment.equipment_id == MaintenanceRecord.equipment_id
        )
        .filter(
            Equipment.hospital_id == current_user["hospital_id"]
        )
        .all()
    )


@app.post("/maintenance-records")
def add_maintenance_record(
    record: MaintenanceRecordCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    equipment = db.query(Equipment).filter(
        Equipment.equipment_id == record.equipment_id,
        Equipment.hospital_id == current_user["hospital_id"]
    ).first()

    if not equipment:
        raise HTTPException(
            status_code=404,
            detail="Equipment not found for your hospital"
        )

    return create_maintenance_record(
        db,
        record.equipment_id,
        record.maintenance_date,
        record.maintenance_type,
        record.downtime_hours,
        record.maintenance_cost,
        record.failure_reason,
        record.notes
    )


# =========================================================

# LOGIN

# =========================================================


@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == form_data.username
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not user.password_hash or not verify_password(
        form_data.password, user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    # Reject deactivated accounts
    if not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    token = create_access_token(
        {
            "user_id": user.user_id,
            "role": user.role,
            "hospital_id": user.hospital_id
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@app.get("/admin-test")
def admin_test(current_user: dict = Depends(require_admin)):

    return {
        "message": "Admin access granted",
        "user_id": current_user["user_id"],
        "hospital_id": current_user["hospital_id"],
    }


@app.get("/risk-analysis")
def get_risk_analysis(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):

    hospital_id = current_user["hospital_id"]

    return get_all_risk_analysis(db, hospital_id)



@app.get("/demand-forecasts")
def get_demand_forecasts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    hospital_id = current_user["hospital_id"]
    today = date.today()
    end_date = today + timedelta(days=29)

    rows = (
        db.query(DemandPrediction, Resource)
        .join(
            Resource,
            Resource.resource_id == DemandPrediction.resource_id
        )
        .filter(
            DemandPrediction.hospital_id == hospital_id,
            DemandPrediction.forecast_date >= today,
            DemandPrediction.forecast_date <= end_date,
        )
        .order_by(
            DemandPrediction.forecast_date.asc(),
            DemandPrediction.resource_id.asc(),
        )
        .all()
    )

    forecasts = [
        {
            "prediction_id": prediction.prediction_id,
            "hospital_id": prediction.hospital_id,
            "resource_id": prediction.resource_id,
            "resource_name": resource.resource_name,
            "prediction_date": prediction.prediction_date.isoformat(),
            "forecast_date": prediction.forecast_date.isoformat(),
            "predicted_quantity": prediction.predicted_quantity,
            "model_name": prediction.model_name,
        }
        for prediction, resource in rows
    ]

    return {
        "hospital_id": hospital_id,
        "forecast_period_days": 30,
        "total_forecasts": len(forecasts),
        "forecasts": forecasts,
    }


@app.get("/optimization-inputs")
def get_optimization_inputs(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):

    hospital_id = current_user["hospital_id"]

    inventories = db.query(Inventory).filter(Inventory.hospital_id == hospital_id).all()

    if not inventories:

        raise HTTPException(
            status_code=404, detail="No inventory found for this hospital"
        )

    results = []

    for inventory in inventories:

        resource = (
            db.query(Resource)
            .filter(Resource.resource_id == inventory.resource_id)
            .first()
        )

        if not resource:

            continue

        risk = (
            db.query(RiskAnalysis)
            .filter(
                RiskAnalysis.hospital_id == hospital_id,
                RiskAnalysis.resource_id == inventory.resource_id,
            )
            .order_by(RiskAnalysis.analysis_date.desc())
            .first()
        )

        if not risk:

            continue

        prediction = (
            db.query(DemandPrediction)
            .filter(
                DemandPrediction.hospital_id == hospital_id,
                DemandPrediction.resource_id == inventory.resource_id,
            )
            .order_by(DemandPrediction.forecast_date.desc())
            .first()
        )

        results.append(
            {
                "hospital_id": hospital_id,
                "resource_id": inventory.resource_id,
                "resource_name": resource.resource_name,
                "current_usable_stock": inventory.usable_quantity,
                "predicted_daily_demand": (
                    prediction.predicted_quantity if prediction else None
                ),
                "safety_stock": resource.safety_stock,
                "reorder_level": resource.reorder_level,
                "lead_time_days": resource.lead_time_days,
                "shortage_risk": risk.shortage_risk,
                "wastage_risk": risk.wastage_risk,
                "risk_level": risk.risk_level,
                "expected_stockout_date": (risk.expected_stockout_date),
                "expected_wastage_quantity": (risk.expected_wastage_quantity),
            }
        )

    return {"hospital_id": hospital_id, "optimization_inputs": results}


@app.get("/equipment-risk")
def get_equipment_risk(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):

    hospital_id = current_user["hospital_id"]

    equipments = db.query(Equipment).filter(Equipment.hospital_id == hospital_id).all()

    if not equipments:

        raise HTTPException(
            status_code=404, detail="No equipment found for this hospital"
        )

    results = []

    for equipment in equipments:

        # -----------------------------

        # 1. Equipment Age Score

        # -----------------------------

        if equipment.installation_date:

            age_years = (date.today() - equipment.installation_date).days / 365.25

        else:

            age_years = 0

        if age_years <= 2:

            age_score = 10

        elif age_years <= 5:

            age_score = 30

        elif age_years <= 8:

            age_score = 60

        elif age_years <= 12:

            age_score = 80

        else:

            age_score = 100

        # -----------------------------

        # 2. Utilization Score

        # -----------------------------

        available_hours = equipment.available_hours or 0

        utilization_hours = equipment.utilization_hours or 0

        if available_hours > 0:

            utilization_percentage = (utilization_hours / available_hours) * 100

        else:

            utilization_percentage = 0

        if utilization_percentage <= 40:

            utilization_score = 20

        elif utilization_percentage <= 60:

            utilization_score = 40

        elif utilization_percentage <= 80:

            utilization_score = 60

        elif utilization_percentage <= 90:

            utilization_score = 80

        else:

            utilization_score = 100

        # -----------------------------

        # 3. Maintenance & Downtime

        # -----------------------------

        maintenance_records = (
            db.query(MaintenanceRecord)
            .filter(MaintenanceRecord.equipment_id == equipment.equipment_id)
            .all()
        )

        maintenance_count = len(maintenance_records)

        total_downtime = sum(
            float(record.downtime_hours or 0) for record in maintenance_records
        )

        if total_downtime <= 5:

            downtime_score = 20

        elif total_downtime <= 20:

            downtime_score = 40

        elif total_downtime <= 50:

            downtime_score = 70

        elif total_downtime <= 100:

            downtime_score = 85

        else:

            downtime_score = 100

        # -----------------------------

        # 4. Failure History Score

        # -----------------------------

        failure_count = sum(
            1 for record in maintenance_records if record.failure_reason
        )

        if failure_count == 0:

            failure_score = 10

        elif failure_count == 1:

            failure_score = 40

        elif failure_count == 2:

            failure_score = 65

        elif failure_count == 3:

            failure_score = 80

        else:

            failure_score = 100

        # -----------------------------

        # Final Risk Score

        # -----------------------------

        risk_score = (
            age_score * 0.25
            + utilization_score * 0.25
            + downtime_score * 0.25
            + failure_score * 0.25
        )

        # -----------------------------

        # Risk Level

        # -----------------------------

        if risk_score < 25:

            risk_level = "LOW"

        elif risk_score < 50:

            risk_level = "MEDIUM"

        elif risk_score < 75:

            risk_level = "HIGH"

        else:

            risk_level = "CRITICAL"

        # -----------------------------

        # Maintenance Priority

        # -----------------------------

        if risk_score >= 75:

            maintenance_priority = "URGENT"

        elif risk_score >= 50:

            maintenance_priority = "HIGH"

        elif risk_score >= 25:

            maintenance_priority = "MEDIUM"

        else:

            maintenance_priority = "LOW"

        if maintenance_priority == "URGENT":

            maintenance_action = "Immediate maintenance review required"

        elif maintenance_priority == "HIGH":

            maintenance_action = "Maintenance should be planned soon"

        elif maintenance_priority == "MEDIUM":

            maintenance_action = "Schedule preventive maintenance"

        else:

            maintenance_action = "Continue routine monitoring"

        results.append(
            {
                "equipment_id": equipment.equipment_id,
                "equipment_name": equipment.equipment_name,
                "equipment_type": equipment.equipment_type,
                "status": equipment.status,
                "equipment_age_years": round(age_years, 2),
                "utilization_hours": float(utilization_hours),
                "available_hours": float(available_hours),
                "utilization_percentage": round(utilization_percentage, 2),
                "maintenance_count": maintenance_count,
                "failure_count": failure_count,
                "total_downtime_hours": round(total_downtime, 2),
                "age_score": age_score,
                "utilization_score": utilization_score,
                "downtime_score": downtime_score,
                "failure_score": failure_score,
                "risk_score": round(risk_score, 2),
                "risk_level": risk_level,
                "maintenance_priority": maintenance_priority,
                "maintenance_action": maintenance_action,
            }
        )

    return {
        "hospital_id": hospital_id,
        "total_equipment": len(results),
        "results": results,
    }


@app.post("/risk-analysis/run")
def run_risk_analysis(
    db: Session = Depends(get_db), current_user: dict = Depends(require_admin)
):

    hospital_id = current_user["hospital_id"]

    # ---------------------------------

    # GET HOSPITAL INVENTORY

    # ---------------------------------

    inventories = db.query(Inventory).filter(Inventory.hospital_id == hospital_id).all()

    if not inventories:

        raise HTTPException(
            status_code=404, detail="No inventory found for this hospital"
        )

    results = []

    for inventory in inventories:

        resource = (
            db.query(Resource)
            .filter(Resource.resource_id == inventory.resource_id)
            .first()
        )

        if not resource:
            continue

        # ---------------------------------
        # GET FUTURE DEMAND FORECASTS
        # ---------------------------------

        today = date.today()

        forecast_rows = (
            db.query(DemandPrediction)
            .filter(
                DemandPrediction.hospital_id == hospital_id,
                DemandPrediction.resource_id == inventory.resource_id,
                DemandPrediction.forecast_date >= today,
                DemandPrediction.forecast_date <= today + timedelta(days=29),
            )
            .order_by(DemandPrediction.forecast_date.asc())
            .all()
        )

        forecast_map = {
            row.forecast_date: float(row.predicted_quantity) for row in forecast_rows
        }

        # Ensure all 30 forecast dates are available
        required_dates = [today + timedelta(days=i) for i in range(30)]

        if not all(d in forecast_map for d in required_dates):
            continue

        # Calculate forecasted demand
        demand_7_days = sum(forecast_map[today + timedelta(days=i)] for i in range(7))

        demand_30_days = sum(forecast_map[today + timedelta(days=i)] for i in range(30))

        # Average daily demand for risk calculations
        shortage_daily_demand = demand_7_days / 7
        wastage_daily_demand = demand_30_days / 30

        predicted_daily_demand = shortage_daily_demand

        # ---------------------------------

        # SHORTAGE RISK

        # ---------------------------------

        print(
    "DEBUG:",
    "Usable Stock =", inventory.usable_quantity,
    "Daily Demand =", shortage_daily_demand,
    "Lead Time =", resource.lead_time_days,
    "Safety Stock =", resource.safety_stock
)

        shortage = calculate_shortage_risk(
            current_stock=inventory.usable_quantity,
            predicted_daily_demand=shortage_daily_demand,
            lead_time_days=resource.lead_time_days,
            safety_stock=resource.safety_stock,
        )

        # ---------------------------------

        # CALCULATE SHORTAGE RISK %

        # ---------------------------------

        shortage_risk_percentage = (
            max(0, -shortage["stock_gap"]) / shortage["required_stock"] * 100
            if shortage["required_stock"] > 0
            else 0
        )

        # ---------------------------------

        # EARLIEST EXPIRY BATCH

        # ---------------------------------

        earliest_batch = (
            db.query(ResourceBatch)
            .filter(ResourceBatch.inventory_id == inventory.inventory_id)
            .order_by(ResourceBatch.expiry_date.asc())
            .first()
        )

        if earliest_batch:

            days_until_expiry = (earliest_batch.expiry_date - date.today()).days

        else:

            days_until_expiry = 9999

        # ---------------------------------

        # WASTAGE RISK

        # ---------------------------------

        wastage = calculate_wastage_risk(
            current_stock=inventory.usable_quantity,
            predicted_daily_demand=wastage_daily_demand,
            days_until_expiry=max(days_until_expiry, 0),
        )

        # ---------------------------------

        # OVERALL RISK

        # ---------------------------------

        risk_levels = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

        if risk_levels[shortage["risk_level"]] >= risk_levels[wastage["risk_level"]]:

            overall_risk = shortage["risk_level"]

        else:

            overall_risk = wastage["risk_level"]

        # ---------------------------------

        # EXPECTED STOCKOUT DATE

        # ---------------------------------

        if shortage["days_of_stock"] != float("inf"):

            expected_stockout_date = date.today() + timedelta(
                days=int(shortage["days_of_stock"])
            )

        else:

            expected_stockout_date = None

        # ---------------------------------

        # SAVE RISK ANALYSIS

        # ---------------------------------

        create_risk_analysis(
            db=db,
            hospital_id=hospital_id,
            resource_id=inventory.resource_id,
            shortage_risk=float(shortage_risk_percentage),
            wastage_risk=float(wastage["wastage_percentage"]),
            risk_level=overall_risk,
            expected_stockout_date=expected_stockout_date,
            expected_wastage_quantity=float(wastage["expected_wastage"]),
        )

        # ---------------------------------

        # RESPONSE DATA

        # ---------------------------------

        results.append(
            {
                "hospital_id": hospital_id,
                "resource_id": inventory.resource_id,
                "predicted_daily_demand": predicted_daily_demand,
                "shortage_risk": shortage,
                "shortage_risk_percentage": round(shortage_risk_percentage, 2),
                "wastage_risk": wastage,
                "overall_risk": overall_risk,
            }
        )

    # ---------------------------------

    # COMMIT ALL RECORDS

    # ---------------------------------

    db.commit()

    return {"message": "Risk analysis completed successfully", "results": results}



@app.get("/risk-alerts")
def get_risk_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    hospital_id = current_user["hospital_id"]

    # Find the latest risk analysis for each resource
    latest_risk_ids = (
        db.query(
            func.max(RiskAnalysis.risk_id).label("latest_risk_id")
        )
        .filter(RiskAnalysis.hospital_id == hospital_id)
        .group_by(RiskAnalysis.resource_id)
        .subquery()
    )

    risks = (
        db.query(RiskAnalysis)
        .join(
            latest_risk_ids,
            RiskAnalysis.risk_id == latest_risk_ids.c.latest_risk_id,
        )
        .filter(
            RiskAnalysis.hospital_id == hospital_id,
            RiskAnalysis.risk_level.in_(["HIGH", "CRITICAL"]),
        )
        .order_by(RiskAnalysis.analysis_date.desc())
        .all()
    )

    alerts = []

    for risk in risks:
        resource = (
            db.query(Resource)
            .filter(Resource.resource_id == risk.resource_id)
            .first()
        )

        alerts.append({
            "risk_id": risk.risk_id,
            "resource_id": risk.resource_id,
            "resource_name": resource.resource_name if resource else "Unknown",
            "risk_level": risk.risk_level,
            "shortage_risk": risk.shortage_risk,
            "wastage_risk": risk.wastage_risk,
            "expected_stockout_date": risk.expected_stockout_date,
            "expected_wastage_quantity": risk.expected_wastage_quantity,
            "message": (
                f"{risk.risk_level} risk detected for "
                f"{resource.resource_name if resource else 'resource'}"
            ),
        })

    return {
        "hospital_id": hospital_id,
        "total_alerts": len(alerts),
        "alerts": alerts,
    }


@app.get("/recommendations")
def get_recommendations(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user["hospital_id"]

    recommendations = (
        db.query(Recommendation)
        .filter(Recommendation.hospital_id == hospital_id)
        .order_by(Recommendation.recommendation_id.desc())
        .all()
    )

    result = []

    for recommendation in recommendations:
        resource = None
        equipment = None

        if recommendation.resource_id is not None:
            resource = (
                db.query(Resource)
                .filter(Resource.resource_id == recommendation.resource_id)
                .first()
            )

        if recommendation.equipment_id is not None:
            equipment = (
                db.query(Equipment)
                .filter(Equipment.equipment_id == recommendation.equipment_id)
                .first()
            )

        result.append(
            {
                "recommendation_id": recommendation.recommendation_id,
                "hospital_id": recommendation.hospital_id,
                "recommendation_type": recommendation.recommendation_type,
                "resource_id": recommendation.resource_id,
                "resource_name": (resource.resource_name if resource else None),
                "equipment_id": recommendation.equipment_id,
                "equipment_name": (equipment.equipment_name if equipment else None),
                "recommended_quantity": recommendation.recommended_quantity,
                "source_hospital_id": recommendation.source_hospital_id,
                "target_hospital_id": recommendation.target_hospital_id,
                "priority": recommendation.priority,
                "reason": recommendation.reason,
                "status": recommendation.status,
                "rejection_reason": recommendation.rejection_reason,
            }
        )

    return {"hospital_id": hospital_id, "total": len(result), "recommendations": result}


@app.post("/recommendations/generate")
def generate_recommendations(
    db: Session = Depends(get_db), current_user: dict = Depends(require_central_admin)
):
    hospital_id = current_user["hospital_id"]

    # Run the existing OR-Tools optimizer.
    optimization_response = _run_global_optimization(
        db,
        hospital_id
    )

    optimization = optimization_response["optimization"]

    recommendations = []

    def already_exists(
        recommendation_type,
        resource_id=None,
        source_hospital_id=None,
        target_hospital_id=None,
        equipment_id=None,
    ):
        query = db.query(Recommendation).filter(
            Recommendation.hospital_id == hospital_id,
            Recommendation.recommendation_type == recommendation_type,
            Recommendation.status == "PENDING",
        )

        if resource_id is not None:
            query = query.filter(Recommendation.resource_id == resource_id)

        if source_hospital_id is not None:
            query = query.filter(
                Recommendation.source_hospital_id == source_hospital_id
            )

        if target_hospital_id is not None:
            query = query.filter(
                Recommendation.target_hospital_id == target_hospital_id
            )

        if equipment_id is not None:
            query = query.filter(Recommendation.equipment_id == equipment_id)

        return query.first() is not None

    def get_resource_priority(resource):
        """Return priority and an auditable explanation from the latest risk row."""
        risk = (
            db.query(RiskAnalysis)
            .filter(
                RiskAnalysis.hospital_id == hospital_id,
                RiskAnalysis.resource_id == resource.resource_id,
            )
            .order_by(
                RiskAnalysis.analysis_date.desc(),
                RiskAnalysis.risk_id.desc(),
            )
            .first()
        )

        criticality = (getattr(resource, "criticality", None) or "MEDIUM").upper()

        if risk is None:
            # Do not silently label an unassessed resource LOW priority.
            return (
                "MEDIUM",
                (
                    f"Recommended quantity is based on optimization. "
                    f"Resource criticality is {criticality}. No risk analysis "
                    f"is available, so MEDIUM priority is assigned pending assessment."
                ),
            )

        shortage_risk = float(risk.shortage_risk or 0)
        wastage_risk = float(risk.wastage_risk or 0)

        priority = calculate_recommendation_priority(
            shortage_risk=shortage_risk,
            wastage_risk=wastage_risk,
            criticality=criticality,
        )

        reason = (
            f"Latest risk assessment: shortage risk {shortage_risk:.1f}%, "
            f"wastage risk {wastage_risk:.1f}%; resource criticality "
            f"{criticality}. Priority set to {priority} using the configured "
            f"risk thresholds and criticality escalation."
        )
        return priority, reason

    # ---------------------------------------------------------
    # 1. PROCUREMENT RECOMMENDATIONS
    # ---------------------------------------------------------
    for item in optimization.get("procurement", []):
        if item["hospital_id"] != hospital_id:
            continue

        resource_id = item["resource_id"]
        quantity = item["quantity"]

        if quantity <= 0:
            continue

        if already_exists("PROCUREMENT", resource_id=resource_id):
            continue

        resource = (
            db.query(Resource)
            .filter(Resource.resource_id == resource_id)
            .first()
        )
        if resource is None:
            continue

        priority, risk_reason = get_resource_priority(resource)
        reason = (
            f"Procurement of {quantity:g} {resource.unit} is recommended "
            f"to cover the remaining requirement after available stock and "
            f"inter-hospital redistribution were considered. {risk_reason}"
        )

        recommendation = Recommendation(
            hospital_id=hospital_id,
            resource_id=resource_id,
            recommendation_type="PROCUREMENT",
            recommended_quantity=quantity,
            priority=priority,
            reason=reason,
            status="PENDING",
        )
        db.add(recommendation)

        recommendations.append(
            {
                "recommendation_type": "PROCUREMENT",
                "resource_id": resource_id,
                "resource_name": resource.resource_name,
                "recommended_quantity": quantity,
                "priority": priority,
                "reason": reason,
                "status": "PENDING",
            }
        )

    # ---------------------------------------------------------
    # 2. REDISTRIBUTION RECOMMENDATIONS
    # ---------------------------------------------------------
    for item in optimization.get("redistribution", []):
        source_hospital_id = item["source_hospital_id"]
        target_hospital_id = item["target_hospital_id"]
        resource_id = item["resource_id"]
        quantity = item["quantity"]

        # Create the recommendation only for its receiving hospital.
        if target_hospital_id != hospital_id or quantity <= 0:
            continue

        if already_exists(
            "REDISTRIBUTION",
            resource_id=resource_id,
            source_hospital_id=source_hospital_id,
            target_hospital_id=target_hospital_id,
        ):
            continue

        resource = (
            db.query(Resource)
            .filter(Resource.resource_id == resource_id)
            .first()
        )
        if resource is None:
            continue

        priority, risk_reason = get_resource_priority(resource)
        reason = (
            f"Redistribution of {quantity:g} {resource.unit} from hospital "
            f"{source_hospital_id} to hospital {target_hospital_id} is "
            f"recommended because the optimizer identified transferable "
            f"surplus stock. {risk_reason}"
        )

        recommendation = Recommendation(
            hospital_id=hospital_id,
            resource_id=resource_id,
            recommendation_type="REDISTRIBUTION",
            recommended_quantity=quantity,
            source_hospital_id=source_hospital_id,
            target_hospital_id=target_hospital_id,
            priority=priority,
            reason=reason,
            status="PENDING",
        )
        db.add(recommendation)

        recommendations.append(
            {
                "recommendation_type": "REDISTRIBUTION",
                "resource_id": resource_id,
                "resource_name": resource.resource_name,
                "recommended_quantity": quantity,
                "source_hospital_id": source_hospital_id,
                "target_hospital_id": target_hospital_id,
                "priority": priority,
                "reason": reason,
                "status": "PENDING",
            }
        )

    # ---------------------------------------------------------
    # 3. MAINTENANCE RECOMMENDATIONS
    # ---------------------------------------------------------
    for item in optimization.get("maintenance", []):
        equipment_id = item["equipment_id"]

        if item["hospital_id"] != hospital_id:
            continue

        if already_exists("MAINTENANCE", equipment_id=equipment_id):
            continue

        equipment = (
            db.query(Equipment)
            .filter(Equipment.equipment_id == equipment_id)
            .first()
        )
        if equipment is None:
            continue

        # Maintenance priority remains independent of resource risk scoring.
        # Equipment-specific risk/criticality scoring can be added separately.
        priority = "HIGH"
        reason = (
            "Optimization recommends scheduling maintenance to reduce "
            "avoidable equipment downtime."
        )

        recommendation = Recommendation(
            hospital_id=hospital_id,
            resource_id=None,
            recommendation_type="MAINTENANCE",
            recommended_quantity=1,
            equipment_id=equipment_id,
            priority=priority,
            reason=reason,
            status="PENDING",
        )
        db.add(recommendation)

        recommendations.append(
            {
                "recommendation_type": "MAINTENANCE",
                "equipment_id": equipment_id,
                "equipment_name": equipment.equipment_name,
                "recommended_quantity": 1,
                "maintenance_cost": item.get("maintenance_cost", 0),
                "avoidable_downtime_hours": item.get(
                    "avoidable_downtime_hours", 0
                ),
                "priority": priority,
                "reason": reason,
                "status": "PENDING",
            }
        )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Recommendations generated from optimization",
        "hospital_id": hospital_id,
        "recommendations": recommendations,
    }


# =========================================================

# RESOURCE ALLOCATION OPTIMIZATION

# =========================================================


@app.post("/recommendations/{recommendation_id}/approve")
def approve_recommendation(
    recommendation_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    hospital_id = current_user["hospital_id"]

    recommendation = (
        db.query(Recommendation)
        .filter(
            Recommendation.recommendation_id == recommendation_id,
            Recommendation.hospital_id == hospital_id,
        )
        .with_for_update()
        .first()
    )

    if not recommendation:
        raise HTTPException(404, "Recommendation not found")

    try:
        if recommendation.recommendation_type == "REDISTRIBUTION":
            if recommendation.status != "SOURCE_APPROVED":
                raise HTTPException(400, "Source hospital approval is required first.")

            result = execute_approved_redistribution(
                db=db, recommendation=recommendation
            )

            return {
                "message": "Redistribution approved and executed",
                "recommendation_id": recommendation_id,
                "status": "EXECUTED",
                "details": result,
            }

        if recommendation.status != "PENDING":
            raise HTTPException(400, "Only PENDING recommendations can be approved.")

        if recommendation.recommendation_type not in ("PROCUREMENT", "MAINTENANCE"):
            raise HTTPException(400, "Unsupported recommendation type.")

        recommendation.status = "APPROVED"
        db.commit()
        db.refresh(recommendation)

        return {
            "message": "Recommendation approved successfully",
            "recommendation_id": recommendation_id,
            "status": recommendation.status,
        }

    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc))


@app.post("/recommendations/{recommendation_id}/source-approve")
def source_approve_recommendation(
    recommendation_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    source_hospital_id = current_user["hospital_id"]

    recommendation = (
        db.query(Recommendation)
        .filter(
            Recommendation.recommendation_id == recommendation_id,
            Recommendation.source_hospital_id == source_hospital_id,
            Recommendation.recommendation_type == "REDISTRIBUTION",
        )
        .first()
    )

    if not recommendation:
        raise HTTPException(404, "Redistribution recommendation not found.")

    try:
        result = approve_source_redistribution(
            db=db,
            recommendation_id=recommendation_id,
            source_hospital_id=source_hospital_id,
        )

        return {
            "message": "Source hospital approval recorded",
            "recommendation_id": recommendation_id,
            "status": "SOURCE_APPROVED",
            "details": result,
        }

    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc))


@app.post("/recommendations/{recommendation_id}/receive")
def receive_procurement_recommendation(
    recommendation_id: int,
    receipt: ProcurementReceiptCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    hospital_id = current_user["hospital_id"]

    recommendation = (
        db.query(Recommendation)
        .filter(
            Recommendation.recommendation_id == recommendation_id,
            Recommendation.hospital_id == hospital_id,
            Recommendation.recommendation_type == "PROCUREMENT",
        )
        .first()
    )

    if not recommendation:
        raise HTTPException(404, "Procurement recommendation not found.")

    try:
        result = receive_procurement(
            db=db,
            recommendation_id=recommendation_id,
            hospital_id=hospital_id,
            batch_number=receipt.batch_number,
            expiry_date=receipt.expiry_date,
            manufacturing_date=receipt.manufacturing_date,
            received_date=receipt.received_date,
        )

        return {
            "message": "Procurement batch received successfully",
            "recommendation_id": recommendation_id,
            "status": "RECEIVED",
            "details": result,
        }

    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc))


class RejectRecommendationRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=1, max_length=1000)


@app.post("/recommendations/{recommendation_id}/reject")
def reject_recommendation(
    recommendation_id: int,
    payload: RejectRecommendationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    hospital_id = current_user["hospital_id"]
    rejection_reason = payload.rejection_reason.strip()

    if not rejection_reason:
        raise HTTPException(
            status_code=422,
            detail="Rejection reason cannot be empty or whitespace.",
        )

    recommendation = (
        db.query(Recommendation)
        .filter(
            Recommendation.recommendation_id == recommendation_id,
            Recommendation.hospital_id == hospital_id,
        )
        .with_for_update()
        .first()
    )

    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    if recommendation.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail="Only PENDING recommendations can be rejected.",
        )

    try:
        recommendation.status = "REJECTED"
        recommendation.rejection_reason = rejection_reason
        db.commit()
        db.refresh(recommendation)
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Recommendation rejected successfully",
        "recommendation_id": recommendation.recommendation_id,
        "status": recommendation.status,
        "rejection_reason": recommendation.rejection_reason,
    }



def _run_global_optimization(db: Session, requested_by_hospital=None):

    inventories = db.query(Inventory).all()

    if not inventories:
        raise HTTPException(
            status_code=404,
            detail="No inventory data found"
        )

    inventory_data = []
    demand_data = {}
    procurement_costs = {}
    expiry_data = {}
    equipment_data = []
    planning_horizon_days = 7

    # Synthetic demo route cost.
    # Replace with persisted route costs when transport-cost data is added.
    transport_costs = {(3, 1): 5}

    today = date.today()

    # ---------------------------------------------------------
    # 1. INVENTORY, DEMAND, PROCUREMENT AND EXPIRY DATA
    # ---------------------------------------------------------

    for inventory in inventories:

        resource = (
            db.query(Resource)
            .filter(Resource.resource_id == inventory.resource_id)
            .first()
        )

        if resource is None:
            continue

        forecast_rows = (
            db.query(DemandPrediction)
            .filter(
                DemandPrediction.hospital_id == inventory.hospital_id,
                DemandPrediction.resource_id == inventory.resource_id,
                DemandPrediction.forecast_date >= today,
                DemandPrediction.forecast_date <= today + timedelta(days=29),
            )
            .order_by(DemandPrediction.forecast_date.asc())
            .all()
        )

        forecast_map = {
            row.forecast_date: float(row.predicted_quantity)
            for row in forecast_rows
        }

        expected_dates = [
            today + timedelta(days=i) for i in range(30)
        ]

        missing_dates = [
            forecast_date
            for forecast_date in expected_dates
            if forecast_date not in forecast_map
        ]

        if missing_dates:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient forecast data for hospital "
                    f"{inventory.hospital_id}, resource "
                    f"{inventory.resource_id}. Missing "
                    f"{len(missing_dates)} of the next 30 "
                    "forecast dates. Generate forecasts first."
                ),
            )

        demand_7_days = sum(
            forecast_map[today + timedelta(days=i)]
            for i in range(7)
        )

        predicted_daily_demand = demand_7_days / 7.0
        safety_stock = max(0, int(resource.safety_stock or 0))
        required_stock = int(round(demand_7_days)) + safety_stock

        demand_key = (
            inventory.hospital_id,
            inventory.resource_id
        )

        demand_data[demand_key] = predicted_daily_demand

        if resource.supplier_id:

            supplier = (
                db.query(Supplier)
                .filter(Supplier.supplier_id == resource.supplier_id)
                .first()
            )

            if supplier and supplier.procurement_cost_per_unit is not None:
                procurement_costs[resource.resource_id] = float(
                    supplier.procurement_cost_per_unit
                )

        # Get resource batches in FEFO order.
        batches = (
            db.query(ResourceBatch)
            .filter(
                ResourceBatch.inventory_id == inventory.inventory_id
            )
            .order_by(
                ResourceBatch.expiry_date.asc(),
                ResourceBatch.batch_id.asc()
            )
            .all()
        )

        batch_data = []

        for batch in batches:

            quantity = max(0, int(batch.quantity or 0))
            reserved_quantity = max(
                0, int(batch.reserved_quantity or 0)
            )

            if reserved_quantity > quantity:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Batch {batch.batch_id} has reserved "
                        "quantity greater than total quantity."
                    ),
                )

            batch_data.append(
                {
                    "batch_id": batch.batch_id,
                    "batch_number": batch.batch_number,
                    "quantity": quantity,
                    "reserved_quantity": reserved_quantity,
                    "available_quantity": quantity - reserved_quantity,
                    "expiry_date": batch.expiry_date.isoformat(),
                    "days_until_expiry": (
                        batch.expiry_date - today
                    ).days,
                }
            )

        expiry_data[demand_key] = batch_data

        # When batch rows exist, the optimizer derives eligible
        # stock from their quantities, excluding expired and reserved units.
        inventory_data.append(
            {
                "hospital_id": inventory.hospital_id,
                "resource_id": inventory.resource_id,
                "usable_stock": int(inventory.usable_quantity or 0),
                "required_stock": required_stock,
                "transferable_stock": max(
                    0,
                    int(inventory.usable_quantity or 0) - required_stock
                ),
                "consumption_required": int(round(demand_7_days)),
                "safety_stock": safety_stock,
                "lead_time_days": int(resource.lead_time_days or 0),
            }
        )

    # ---------------------------------------------------------
    # 2. EQUIPMENT AND MAINTENANCE DATA
    # ---------------------------------------------------------

    equipments = db.query(Equipment).all()

    for equipment in equipments:

        records = (
            db.query(MaintenanceRecord)
            .filter(
                MaintenanceRecord.equipment_id == equipment.equipment_id
            )
            .all()
        )

        costs = [
            float(record.maintenance_cost)
            for record in records
            if record.maintenance_cost is not None
        ]

        estimated_maintenance_cost = (
            sum(costs) / len(costs) if costs else 0.0
        )

        avoidable_downtime_hours = sum(
            float(record.downtime_hours or 0)
            for record in records
            if record.failure_reason
        )

        equipment_data.append(
            {
                "equipment_id": equipment.equipment_id,
                "hospital_id": equipment.hospital_id,
                "criticality": (
                    equipment.criticality or "MEDIUM"
                ).upper(),
                "maintenance_cost": estimated_maintenance_cost,
                "avoidable_downtime_hours": avoidable_downtime_hours,
            }
        )

    # ---------------------------------------------------------
    # 3. RUN OPTIMIZATION
    # ---------------------------------------------------------

    # Run optimization after collecting data for ALL equipment.
    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data=demand_data,
        procurement_costs=procurement_costs,
        transport_costs=transport_costs,
        expiry_data=expiry_data,
        planning_horizon_days=planning_horizon_days,
        equipment_data=equipment_data,
    )

    expiry_inputs_response = [
        {
            "hospital_id": key[0],
            "resource_id": key[1],
            "batches": batches,
        }
        for key, batches in expiry_data.items()
    ]

    return {
        "requested_by_hospital": requested_by_hospital,
        "planning_horizon_days": planning_horizon_days,
        "inventory_inputs": inventory_data,
        "expiry_inputs": expiry_inputs_response,
        "equipment_inputs": equipment_data,
        "optimization": result,
    }


# ---------------------------------------------------------
# RESOURCE ALLOCATION OPTIMIZATION API
# ---------------------------------------------------------

@app.get("/optimize-allocation")
def optimize_allocation(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_central_admin)
):
    return _run_global_optimization(
        db,
        current_user["hospital_id"]
    )



@app.get("/dashboard/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    hospital_id = current_user["hospital_id"]
    today = date.today()
    expiry_cutoff = today + timedelta(days=30)

    # Inventory and stock metrics for the logged-in hospital.
    inventory_rows = (
        db.query(Inventory, Resource)
        .join(Resource, Resource.resource_id == Inventory.resource_id)
        .filter(Inventory.hospital_id == hospital_id)
        .all()
    )

    low_stock_items = []
    total_current_stock = 0
    total_usable_stock = 0
    resource_ids = set()

    for inventory, resource in inventory_rows:
        current_quantity = int(inventory.current_quantity or 0)
        usable_quantity = int(inventory.usable_quantity or 0)
        total_current_stock += current_quantity
        total_usable_stock += usable_quantity
        resource_ids.add(resource.resource_id)

        if usable_quantity <= int(resource.reorder_level or 0):
            low_stock_items.append(
                {
                    "inventory_id": inventory.inventory_id,
                    "resource_id": resource.resource_id,
                    "resource_name": resource.resource_name,
                    "current_quantity": current_quantity,
                    "usable_quantity": usable_quantity,
                    "reorder_level": resource.reorder_level,
                    "unit": resource.unit,
                }
            )

    # Batch expiry information, scoped through the hospital's inventory.
    batch_rows = (
        db.query(ResourceBatch, Inventory, Resource)
        .join(Inventory, Inventory.inventory_id == ResourceBatch.inventory_id)
        .join(Resource, Resource.resource_id == Inventory.resource_id)
        .filter(Inventory.hospital_id == hospital_id)
        .all()
    )

    expired_batches = []
    expiring_batches = []

    for batch, inventory, resource in batch_rows:
        item = {
            "batch_id": batch.batch_id,
            "batch_number": batch.batch_number,
            "resource_id": resource.resource_id,
            "resource_name": resource.resource_name,
            "quantity": batch.quantity,
            "expiry_date": batch.expiry_date,
            "days_until_expiry": (batch.expiry_date - today).days,
        }
        if batch.expiry_date < today:
            expired_batches.append(item)
        elif batch.expiry_date <= expiry_cutoff:
            expiring_batches.append(item)

    # Count only the latest risk record per resource to avoid counting
    # historical analyses as separate current alerts.
    risk_rows = (
        db.query(RiskAnalysis)
        .filter(RiskAnalysis.hospital_id == hospital_id)
        .order_by(RiskAnalysis.analysis_date.desc(), RiskAnalysis.risk_id.desc())
        .all()
    )
    latest_risk_by_resource = {}
    for risk in risk_rows:
        if risk.resource_id not in latest_risk_by_resource:
            latest_risk_by_resource[risk.resource_id] = risk

    high_risk_count = sum(
        1
        for risk in latest_risk_by_resource.values()
        if (risk.risk_level or "").upper() in {"HIGH", "CRITICAL"}
    )

    pending_recommendations = (
        db.query(Recommendation)
        .filter(
            Recommendation.hospital_id == hospital_id,
            Recommendation.status == "PENDING",
        )
        .count()
    )

    equipment_count = (
        db.query(Equipment).filter(Equipment.hospital_id == hospital_id).count()
    )

    return {
        "hospital_id": hospital_id,
        "generated_on": today,
        "total_resources": len(resource_ids),
        "total_inventory_records": len(inventory_rows),
        "total_current_stock": total_current_stock,
        "total_usable_stock": total_usable_stock,
        "low_stock_count": len(low_stock_items),
        "low_stock_items": low_stock_items,
        "expired_batch_count": len(expired_batches),
        "expired_batches": expired_batches,
        "expiring_within_30_days_count": len(expiring_batches),
        "expiring_batches": expiring_batches,
        "high_risk_count": high_risk_count,
        "pending_recommendations": pending_recommendations,
        "total_equipment": equipment_count,
    }