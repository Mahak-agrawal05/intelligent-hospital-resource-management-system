from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text

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
    Recommendation
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
    MaintenanceRecordCreate
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
    get_all_risk_analysis
)

from security import (
    verify_password,
    create_access_token,
    get_current_user,
    require_admin,
    hash_password
)

app = FastAPI(
    title="Intelligent Hospital Resource Allocation System",
    description="Backend API for hospital resource and inventory management",
    version="1.0.0"
)


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return {
        "message": "Intelligent Hospital Resource System API is running"
    }


# =========================================================
# HOSPITALS
# =========================================================

@app.get("/hospitals")
def get_hospitals(
    db: Session = Depends(get_db)
):

    return get_all_hospitals(db)


@app.post("/hospitals")
def add_hospital(
    hospital: HospitalCreate,
    db: Session = Depends(get_db)
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

@app.get("/users")
def get_users(
    db: Session = Depends(get_db)
):

    return get_all_users(db)


@app.post("/users")
def add_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):

    hashed_password = hash_password(user.password_hash)

    return create_user(
        db,
        user.name,
        user.email,
        hashed_password,
        user.role,
        user.hospital_id
    )


# =========================================================
# RESOURCES
# =========================================================

@app.get("/resources")
def get_resources(
    db: Session = Depends(get_db)
):

    return get_all_resources(db)


@app.post("/resources")
def add_resource(
    resource: ResourceCreate,
    db: Session = Depends(get_db)
):

    return create_resource(
        db,
        resource.resource_name,
        resource.category,
        resource.unit,
        resource.supplier_id,
        resource.reorder_level,
        resource.safety_stock,
        resource.lead_time_days
    )


# =========================================================
# INVENTORY
# =========================================================

@app.get("/inventory")
def get_inventory(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    hospital_id = current_user["hospital_id"]

    return get_all_inventory(
        db,
        hospital_id
    )


@app.post("/inventory")
def add_inventory(
    inventory: InventoryCreate,
    db: Session = Depends(get_db)
):

    if (
        inventory.reserved_quantity
        > inventory.current_quantity
    ):

        raise HTTPException(
            status_code=400,
            detail="Reserved quantity cannot exceed current quantity."
        )

    return create_inventory(
        db,
        inventory.hospital_id,
        inventory.resource_id,
        inventory.current_quantity,
        inventory.reserved_quantity
    )


# =========================================================
# RESOURCE BATCHES
# =========================================================

@app.get("/resource-batches")
def get_resource_batches(
    db: Session = Depends(get_db)
):

    return get_all_batches(db)


@app.post("/resource-batches")
def add_resource_batch(
    batch: ResourceBatchCreate,
    db: Session = Depends(get_db)
):

    return create_batch(
        db,
        batch.inventory_id,
        batch.batch_number,
        batch.quantity,
        batch.manufacturing_date,
        batch.expiry_date,
        batch.received_date
    )


# =========================================================
# CONSUMPTION HISTORY
# =========================================================

@app.get("/consumption-history")
def get_consumption_history(
    db: Session = Depends(get_db)
):

    return get_all_consumption(db)


@app.post("/consumption-history")
def add_consumption_history(
    consumption: ConsumptionHistoryCreate,
    db: Session = Depends(get_db)
):

    return create_consumption(
        db,
        consumption.hospital_id,
        consumption.resource_id,
        consumption.consumption_date,
        consumption.quantity_consumed
    )


# =========================================================
# SUPPLIERS
# =========================================================

@app.get("/suppliers")
def get_suppliers(
    db: Session = Depends(get_db)
):

    return get_all_suppliers(db)


@app.post("/suppliers")
def add_supplier(
    supplier: SupplierCreate,
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db)
):

    return get_all_equipment(db)


@app.post("/equipment")
def add_equipment(
    equipment: EquipmentCreate,
    db: Session = Depends(get_db)
):

    return create_equipment(
        db,
        equipment.hospital_id,
        equipment.equipment_name,
        equipment.equipment_type,
        equipment.manufacturer,
        equipment.model_number,
        equipment.installation_date,
        equipment.status
    )


# =========================================================
# MAINTENANCE RECORDS
# =========================================================

@app.get("/maintenance-records")
def get_maintenance_records(
    db: Session = Depends(get_db)
):

    return get_all_maintenance_records(db)


@app.post("/maintenance-records")
def add_maintenance_record(
    record: MaintenanceRecordCreate,
    db: Session = Depends(get_db)
):

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

    if not verify_password(
        form_data.password,
        user.password_hash
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    token = create_access_token({
        "user_id": user.user_id,
        "role": user.role,
        "hospital_id": user.hospital_id
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@app.get("/admin-test")
def admin_test(
    current_user: dict = Depends(require_admin)
):
    return {
        "message": "Admin access granted",
        "user_id": current_user["user_id"],
        "hospital_id": current_user["hospital_id"]
    }

@app.get("/risk-analysis")
def get_risk_analysis(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user["hospital_id"]

    return get_all_risk_analysis(
        db,
        hospital_id
    )

@app.get("/optimization-inputs")
def get_optimization_inputs(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user["hospital_id"]

    inventories = db.query(Inventory).filter(
        Inventory.hospital_id == hospital_id
    ).all()

    if not inventories:
        raise HTTPException(
            status_code=404,
            detail="No inventory found for this hospital"
        )

    results = []

    for inventory in inventories:

        resource = db.query(Resource).filter(
            Resource.resource_id == inventory.resource_id
        ).first()

        if not resource:
            continue

        risk = (
            db.query(RiskAnalysis)
            .filter(
                RiskAnalysis.hospital_id == hospital_id,
                RiskAnalysis.resource_id == inventory.resource_id
            )
            .order_by(
                RiskAnalysis.analysis_date.desc()
            )
            .first()
        )

        if not risk:
            continue

        prediction = (
            db.query(DemandPrediction)
            .filter(
                DemandPrediction.hospital_id == hospital_id,
                DemandPrediction.resource_id == inventory.resource_id
            )
            .order_by(
                DemandPrediction.forecast_date.desc()
            )
            .first()
        )

        results.append({
            "hospital_id": hospital_id,
            "resource_id": inventory.resource_id,
            "resource_name": resource.resource_name,

            "current_usable_stock": inventory.usable_quantity,

            "predicted_daily_demand": (
                prediction.predicted_quantity
                if prediction else None
            ),

            "safety_stock": resource.safety_stock,
            "reorder_level": resource.reorder_level,
            "lead_time_days": resource.lead_time_days,

            "shortage_risk": risk.shortage_risk,
            "wastage_risk": risk.wastage_risk,
            "risk_level": risk.risk_level,

            "expected_stockout_date": (
                risk.expected_stockout_date
            ),

            "expected_wastage_quantity": (
                risk.expected_wastage_quantity
            )
        })

    return {
        "hospital_id": hospital_id,
        "optimization_inputs": results
    }


@app.get("/equipment-risk")
def get_equipment_risk(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user["hospital_id"]

    equipments = db.query(Equipment).filter(
        Equipment.hospital_id == hospital_id
    ).all()

    if not equipments:
        raise HTTPException(
            status_code=404,
            detail="No equipment found for this hospital"
        )

    results = []

    for equipment in equipments:

        # -----------------------------
        # 1. Equipment Age Score
        # -----------------------------
        if equipment.installation_date:
            age_years = (
                date.today() - equipment.installation_date
            ).days / 365.25
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
            utilization_percentage = (
                utilization_hours / available_hours
            ) * 100
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
        maintenance_records = db.query(
            MaintenanceRecord
        ).filter(
            MaintenanceRecord.equipment_id
            == equipment.equipment_id
        ).all()

        maintenance_count = len(maintenance_records)

        total_downtime = sum(
            float(record.downtime_hours or 0)
            for record in maintenance_records
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
            1
            for record in maintenance_records
            if record.failure_reason
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
            maintenance_action = (
        "Immediate maintenance review required"
        )

        elif maintenance_priority == "HIGH":
            maintenance_action = (
        "Maintenance should be planned soon"
        )

        elif maintenance_priority == "MEDIUM":
            maintenance_action = (
        "Schedule preventive maintenance"
        )

        else:
            maintenance_action = (
        "Continue routine monitoring"
    )

        results.append(
            {
            "equipment_id": equipment.equipment_id,
            "equipment_name": equipment.equipment_name,
            "equipment_type": equipment.equipment_type,
            "status": equipment.status,

            "equipment_age_years": round(age_years, 2),

            "utilization_hours": float(utilization_hours),
            "available_hours": float(available_hours),
            "utilization_percentage": round(
                utilization_percentage, 2
            ),

            "maintenance_count": maintenance_count,
            "failure_count": failure_count,
            "total_downtime_hours": round(
                total_downtime, 2
            ),

            "age_score": age_score,
            "utilization_score": utilization_score,
            "downtime_score": downtime_score,
            "failure_score": failure_score,

            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "maintenance_priority": maintenance_priority,
            "maintenance_action": maintenance_action
        })

    return {
        "hospital_id": hospital_id,
        "total_equipment": len(results),
        "results": results
    }

@app.post("/risk-analysis/run")
def run_risk_analysis(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user["hospital_id"]

    # ---------------------------------
    # GET HOSPITAL INVENTORY
    # ---------------------------------

    inventories = db.query(Inventory).filter(
        Inventory.hospital_id == hospital_id
    ).all()

    if not inventories:
        raise HTTPException(
            status_code=404,
            detail="No inventory found for this hospital"
        )

    results = []

    # ---------------------------------
    # ANALYZE EACH INVENTORY
    # ---------------------------------

    for inventory in inventories:

        # Get resource details
        resource = db.query(Resource).filter(
            Resource.resource_id == inventory.resource_id
        ).first()

        if not resource:
            continue

        # ---------------------------------
        # GET LATEST DEMAND PREDICTION
        # ---------------------------------

        prediction = (
            db.query(DemandPrediction)
            .filter(
                DemandPrediction.hospital_id == hospital_id,
                DemandPrediction.resource_id == inventory.resource_id
            )
            .order_by(
                DemandPrediction.forecast_date.desc()
            )
            .first()
        )

        if not prediction:
            continue

        predicted_daily_demand = prediction.predicted_quantity

        # ---------------------------------
        # SHORTAGE RISK
        # ---------------------------------

        shortage = calculate_shortage_risk(
            current_stock=inventory.usable_quantity,
            predicted_daily_demand=predicted_daily_demand,
            lead_time_days=resource.lead_time_days,
            safety_stock=resource.safety_stock
        )

        # ---------------------------------
        # CALCULATE SHORTAGE RISK %
        # ---------------------------------

        shortage_risk_percentage = (
            max(0, -shortage["stock_gap"])
            / shortage["required_stock"]
            * 100
            if shortage["required_stock"] > 0
            else 0
        )

        # ---------------------------------
        # EARLIEST EXPIRY BATCH
        # ---------------------------------

        earliest_batch = (
            db.query(ResourceBatch)
            .filter(
                ResourceBatch.inventory_id == inventory.inventory_id
            )
            .order_by(
                ResourceBatch.expiry_date.asc()
            )
            .first()
        )

        if earliest_batch:
            days_until_expiry = (
                earliest_batch.expiry_date - date.today()
            ).days
        else:
            days_until_expiry = 9999

        # ---------------------------------
        # WASTAGE RISK
        # ---------------------------------

        wastage = calculate_wastage_risk(
            current_stock=inventory.usable_quantity,
            predicted_daily_demand=predicted_daily_demand,
            days_until_expiry=max(days_until_expiry, 0)
        )

        # ---------------------------------
        # OVERALL RISK
        # ---------------------------------

        risk_levels = {
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3,
            "CRITICAL": 4
        }

        if (
            risk_levels[shortage["risk_level"]]
            >= risk_levels[wastage["risk_level"]]
        ):
            overall_risk = shortage["risk_level"]
        else:
            overall_risk = wastage["risk_level"]

        # ---------------------------------
        # EXPECTED STOCKOUT DATE
        # ---------------------------------

        if shortage["days_of_stock"] != float("inf"):
            expected_stockout_date = (
                date.today()
                + timedelta(
                    days=int(shortage["days_of_stock"])
                )
            )
        else:
            expected_stockout_date = None

        # ---------------------------------
        # SAVE RISK ANALYSIS
        # ---------------------------------

        record = RiskAnalysis(
            hospital_id=hospital_id,
            resource_id=inventory.resource_id,
            analysis_date=date.today(),

            shortage_risk=float(
                shortage_risk_percentage
            ),

            wastage_risk=float(
                wastage["wastage_percentage"]
            ),

            risk_level=overall_risk,

            expected_stockout_date=expected_stockout_date,

            expected_wastage_quantity=float(
                wastage["expected_wastage"]
            )
        )

        db.add(record)

        # ---------------------------------
        # RESPONSE DATA
        # ---------------------------------

        results.append({
            "hospital_id": hospital_id,
            "resource_id": inventory.resource_id,
            "predicted_daily_demand": predicted_daily_demand,

            "shortage_risk": shortage,

            "shortage_risk_percentage":
                round(shortage_risk_percentage, 2),

            "wastage_risk": wastage,

            "overall_risk": overall_risk
        })

    # ---------------------------------
    # COMMIT ALL RECORDS
    # ---------------------------------

    db.commit()

    return {
        "message": "Risk analysis completed successfully",
        "results": results
    }

@app.get("/risk-alerts")
def get_risk_alerts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user["hospital_id"]

    risks = (
        db.query(RiskAnalysis)
        .filter(
            RiskAnalysis.hospital_id == hospital_id,
            RiskAnalysis.risk_level.in_(["HIGH", "CRITICAL"])
        )
        .order_by(RiskAnalysis.analysis_date.desc())
        .all()
    )

    alerts = []

    for risk in risks:
        resource = (
            db.query(Resource)
            .filter(
                Resource.resource_id == risk.resource_id
            )
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
            )
        })

    return {
        "hospital_id": hospital_id,
        "total_alerts": len(alerts),
        "alerts": alerts
    }

@app.post("/recommendations/generate")
def generate_recommendations(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user["hospital_id"]

    risks = (
        db.query(RiskAnalysis)
        .filter(
            RiskAnalysis.hospital_id == hospital_id,
            RiskAnalysis.risk_level.in_(["HIGH", "CRITICAL"])
        )
        .order_by(RiskAnalysis.analysis_date.desc())
        .all()
    )

    if not risks:
        return {
            "message": "No high or critical risks found",
            "recommendations": []
        }

    recommendations = []

    for risk in risks:

        # Only shortage-related recommendations for now
        if risk.shortage_risk <= 0:
            continue

        inventory = (
            db.query(Inventory)
            .filter(
                Inventory.hospital_id == hospital_id,
                Inventory.resource_id == risk.resource_id
            )
            .first()
        )

        resource = (
            db.query(Resource)
            .filter(
                Resource.resource_id == risk.resource_id
            )
            .first()
        )

        if not inventory or not resource:
            continue

        prediction = (
            db.query(DemandPrediction)
            .filter(
                DemandPrediction.hospital_id == hospital_id,
                DemandPrediction.resource_id == risk.resource_id
            )
            .order_by(DemandPrediction.forecast_date.desc())
            .first()
        )

        if not prediction:
            continue

        required_stock = (
            prediction.predicted_quantity * resource.lead_time_days
            + resource.safety_stock
        )

        stock_gap = (
            required_stock - inventory.usable_quantity
        )

        if stock_gap <= 0:
            continue

        recommended_quantity = int(round(stock_gap))

        recommendation = Recommendation(
            hospital_id=hospital_id,
            resource_id=risk.resource_id,
            recommendation_type="PROCUREMENT",
            recommended_quantity=recommended_quantity,
            reason=(
                f"{risk.risk_level} shortage risk detected. "
                f"Current usable stock is {inventory.usable_quantity}, "
                f"while estimated required stock is "
                f"{round(required_stock, 2)}."
            ),
            status="PENDING"
        )

        db.add(recommendation)

        recommendations.append({
            "resource_id": risk.resource_id,
            "resource_name": resource.resource_name,
            "recommendation_type": "PROCUREMENT",
            "recommended_quantity": recommended_quantity,
            "risk_level": risk.risk_level,
            "status": "PENDING"
        })

    db.commit()

    return {
        "message": "Recommendations generated successfully",
        "recommendations": recommendations
    }

@app.get("/recommendations")
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user["hospital_id"]

    recommendations = (
        db.query(Recommendation)
        .filter(
            Recommendation.hospital_id == hospital_id
        )
        .order_by(
            Recommendation.created_at.desc()
        )
        .all()
    )

    return recommendations
# =========================================================
# RESOURCE ALLOCATION OPTIMIZATION
# =========================================================

@app.get("/optimize-allocation")
def optimize_allocation(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    hospital_id = current_user["hospital_id"]

    # ---------------------------------------------------------
    # GET ALL INVENTORY
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # PROCESS INVENTORY
    # ---------------------------------------------------------

    for inventory in inventories:

        resource = db.query(Resource).filter(
            Resource.resource_id == inventory.resource_id
        ).first()

        if not resource:
            continue

        # -----------------------------------------------------
        # LATEST DEMAND PREDICTION
        # -----------------------------------------------------

        prediction = (
            db.query(DemandPrediction)
            .filter(
                DemandPrediction.hospital_id == inventory.hospital_id,
                DemandPrediction.resource_id == inventory.resource_id
            )
            .order_by(
                DemandPrediction.forecast_date.desc()
            )
            .first()
        )

        if prediction:
            predicted_daily_demand = float(
                prediction.predicted_quantity
            )
        else:
            predicted_daily_demand = 0

        # -----------------------------------------------------
        # REQUIRED STOCK
        # -----------------------------------------------------

        required_stock = (
            predicted_daily_demand * 7
            + resource.safety_stock
        )

        # -----------------------------------------------------
        # TRANSFERABLE STOCK
        # -----------------------------------------------------

        transferable_stock = max(
            0,
            inventory.usable_quantity - required_stock
        )

        inventory_data.append({
            "hospital_id": inventory.hospital_id,
            "resource_id": inventory.resource_id,
            "usable_stock": inventory.usable_quantity,
            "required_stock": required_stock,
            "transferable_stock": transferable_stock
        })

        demand_data[
            (
                inventory.hospital_id,
                inventory.resource_id
            )
        ] = predicted_daily_demand

        # -----------------------------------------------------
        # PROCUREMENT COST
        # -----------------------------------------------------

        if resource.supplier_id:

            supplier = db.query(Supplier).filter(
                Supplier.supplier_id == resource.supplier_id
            ).first()

            if supplier:

                procurement_costs[
                    resource.resource_id
                ] = float(
                    supplier.procurement_cost_per_unit or 0
                )

        # -----------------------------------------------------
        # EARLIEST EXPIRY
        # -----------------------------------------------------

        earliest_batch = (
            db.query(ResourceBatch)
            .filter(
                ResourceBatch.inventory_id ==
                inventory.inventory_id
            )
            .order_by(
                ResourceBatch.expiry_date.asc()
            )
            .first()
        )

        if earliest_batch:

            days_until_expiry = (
                earliest_batch.expiry_date
                - date.today()
            ).days

            expiry_data[
                (
                    inventory.hospital_id,
                    inventory.resource_id
                )
            ] = {
                "expiry_date": earliest_batch.expiry_date,
                "days_until_expiry": max(
                    days_until_expiry,
                    0
                ),
                "batch_quantity": earliest_batch.quantity
            }

    # ---------------------------------------------------------
    # TRANSPORTATION COSTS
    # ---------------------------------------------------------

    transport_rows = db.execute(
        text("""
            SELECT
                source_hospital_id,
                target_hospital_id,
                cost_per_unit
            FROM hospital_transport_costs
        """)
    ).fetchall()

    transport_costs = {}

    for row in transport_rows:

        transport_costs[
            (
                row.source_hospital_id,
                row.target_hospital_id
            )
        ] = float(row.cost_per_unit)

    # ---------------------------------------------------------
    # RUN OR-TOOLS OPTIMIZATION
    # ---------------------------------------------------------

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data=demand_data,
        procurement_costs=procurement_costs,
        transport_costs=transport_costs,
        expiry_data=expiry_data,
        planning_horizon_days=7
    )

    # ---------------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------------

    expiry_inputs_response = []

    for key, value in expiry_data.items():

        expiry_inputs_response.append({
            "hospital_id": key[0],
            "resource_id": key[1],
            "expiry_date": value["expiry_date"],
            "days_until_expiry": value["days_until_expiry"],
            "batch_quantity": value["batch_quantity"]
        })

    return {
        "requested_by_hospital": hospital_id,
        "planning_horizon_days": 7,
        "inventory_inputs": inventory_data,
        "expiry_inputs": expiry_inputs_response,
        "optimization": result
    }