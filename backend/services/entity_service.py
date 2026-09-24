from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.entities import (
    Hospital,
    User,
    Resource,
    Inventory,
    ResourceBatch,
    ConsumptionHistory,
    Supplier,
    Equipment,
    MaintenanceRecord,
    RiskAnalysis,
)

from ortools.linear_solver import pywraplp


# =========================================================
# HOSPITAL SERVICES
# =========================================================

def get_all_hospitals(db: Session):
    return db.query(Hospital).all()


def create_hospital(
    db: Session,
    hospital_name: str,
    location: str,
    hospital_type: str
):
    new_hospital = Hospital(
        hospital_name=hospital_name,
        location=location,
        hospital_type=hospital_type
    )

    db.add(new_hospital)
    db.commit()
    db.refresh(new_hospital)

    return new_hospital


# =========================================================
# USER SERVICES
# =========================================================

def get_all_users(db: Session):
    return db.query(User).all()


def create_user(
    db: Session,
    name: str,
    email: str,
    password_hash: str,
    role: str,
    hospital_id: int
):
    new_user = User(
        name=name,
        email=email,
        password_hash=password_hash,
        role=role,
        hospital_id=hospital_id
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# =========================================================
# RESOURCE SERVICES
# =========================================================

def get_all_resources(db: Session):
    return db.query(Resource).all()


def create_resource(
    db: Session,
    resource_name: str,
    category: str,
    unit: str,
    supplier_id: int | None,
    reorder_level: int,
    safety_stock: int,
    lead_time_days: int
):
    new_resource = Resource(
        resource_name=resource_name,
        category=category,
        unit=unit,
        supplier_id=supplier_id,
        reorder_level=reorder_level,
        safety_stock=safety_stock,
        lead_time_days=lead_time_days
    )

    db.add(new_resource)
    db.commit()
    db.refresh(new_resource)

    return new_resource


# =========================================================
# INVENTORY SERVICES
# =========================================================

def get_all_inventory(db: Session, hospital_id: int):
    return db.query(Inventory).filter(
        Inventory.hospital_id == hospital_id
    ).all()


def create_inventory(
    db: Session,
    hospital_id: int,
    resource_id: int,
    current_quantity: int,
    reserved_quantity: int
):
    usable_quantity = current_quantity - reserved_quantity

    new_inventory = Inventory(
        hospital_id=hospital_id,
        resource_id=resource_id,
        current_quantity=current_quantity,
        reserved_quantity=reserved_quantity,
        usable_quantity=usable_quantity,
        last_updated=datetime.now(timezone.utc)
    )

    db.add(new_inventory)
    db.commit()
    db.refresh(new_inventory)

    return new_inventory


# =========================================================
# RESOURCE BATCH SERVICES
# =========================================================

def get_all_batches(db: Session):
    return db.query(ResourceBatch).all()


def create_batch(
    db: Session,
    inventory_id: int,
    batch_number: str,
    quantity: int,
    manufacturing_date,
    expiry_date,
    received_date
):
    new_batch = ResourceBatch(
        inventory_id=inventory_id,
        batch_number=batch_number,
        quantity=quantity,
        manufacturing_date=manufacturing_date,
        expiry_date=expiry_date,
        received_date=received_date
    )

    db.add(new_batch)
    db.commit()
    db.refresh(new_batch)

    return new_batch


# =========================================================
# CONSUMPTION HISTORY SERVICES
# =========================================================

def get_all_consumption(db: Session):
    return db.query(
        ConsumptionHistory
    ).all()


def create_consumption(
    db: Session,
    hospital_id: int,
    resource_id: int,
    consumption_date,
    quantity_consumed: int
):
    new_consumption = ConsumptionHistory(
        hospital_id=hospital_id,
        resource_id=resource_id,
        consumption_date=consumption_date,
        quantity_consumed=quantity_consumed
    )

    db.add(new_consumption)
    db.commit()
    db.refresh(new_consumption)

    return new_consumption


# =========================================================
# SUPPLIER SERVICES
# =========================================================

def get_all_suppliers(db: Session):
    return db.query(Supplier).all()


def create_supplier(
    db: Session,
    supplier_name: str,
    contact_info: str | None,
    average_lead_time: int,
    reliability_score: float | None
):
    new_supplier = Supplier(
        supplier_name=supplier_name,
        contact_info=contact_info,
        average_lead_time=average_lead_time,
        reliability_score=reliability_score
    )

    db.add(new_supplier)
    db.commit()
    db.refresh(new_supplier)

    return new_supplier


# =========================================================
# EQUIPMENT SERVICES
# =========================================================

def get_all_equipment(db: Session):
    return db.query(Equipment).all()


def create_equipment(
    db: Session,
    hospital_id: int,
    equipment_name: str,
    equipment_type: str,
    manufacturer: str | None,
    model_number: str | None,
    installation_date,
    status: str
):
    new_equipment = Equipment(
        hospital_id=hospital_id,
        equipment_name=equipment_name,
        equipment_type=equipment_type,
        manufacturer=manufacturer,
        model_number=model_number,
        installation_date=installation_date,
        status=status
    )

    db.add(new_equipment)
    db.commit()
    db.refresh(new_equipment)

    return new_equipment


# =========================================================
# MAINTENANCE SERVICES
# =========================================================

def get_all_maintenance_records(db: Session):
    return db.query(
        MaintenanceRecord
    ).all()


def create_maintenance_record(
    db: Session,
    equipment_id: int,
    maintenance_date,
    maintenance_type: str,
    downtime_hours: float | None,
    maintenance_cost: float | None,
    failure_reason: str | None,
    notes: str | None
):
    new_record = MaintenanceRecord(
        equipment_id=equipment_id,
        maintenance_date=maintenance_date,
        maintenance_type=maintenance_type,
        downtime_hours=downtime_hours,
        maintenance_cost=maintenance_cost,
        failure_reason=failure_reason,
        notes=notes
    )

    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    return new_record


# =========================================================
# RISK ANALYSIS SERVICES
# =========================================================

def create_risk_analysis(
    db: Session,
    hospital_id,
    resource_id,
    shortage_risk,
    wastage_risk,
    risk_level,
    expected_stockout_date=None,
    expected_wastage_quantity=None
):
    risk = RiskAnalysis(
        hospital_id=hospital_id,
        resource_id=resource_id,
        analysis_date=datetime.today().date(),
        shortage_risk=shortage_risk,
        wastage_risk=wastage_risk,
        risk_level=risk_level,
        expected_stockout_date=expected_stockout_date,
        expected_wastage_quantity=expected_wastage_quantity
    )

    db.add(risk)
    db.commit()
    db.refresh(risk)

    return risk


def get_all_risk_analysis(db, hospital_id):
    return db.query(RiskAnalysis).filter(
        RiskAnalysis.hospital_id == hospital_id
    ).all()


# =========================================================
# RESOURCE ALLOCATION OPTIMIZATION
# =========================================================

def optimize_resource_allocation(
    inventory_data,
    demand_data,
    procurement_costs,
    transport_costs,
    expiry_data=None,
    planning_horizon_days=7
):
    """
    Optimize hospital resource procurement and
    inter-hospital redistribution.

    inventory_data format:

    [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 1100,
            "required_stock": 2050,
            "transferable_stock": 0
        }
    ]

    demand_data format:

    {
        (hospital_id, resource_id): predicted_daily_demand
    }

    procurement_costs format:

    {
        resource_id: cost_per_unit
    }

    transport_costs format:

    {
        (source_hospital_id, target_hospital_id): cost_per_unit
    }

    expiry_data format:

    {
        (hospital_id, resource_id): {
            "expiry_date": "YYYY-MM-DD",
            "days_until_expiry": 10,
            "batch_quantity": 100
        }
    }
    """

    # =====================================================
    # CREATE SOLVER
    # =====================================================

    solver = pywraplp.Solver.CreateSolver("SCIP")

    if not solver:
        raise RuntimeError(
            "OR-Tools SCIP solver could not be created"
        )

    # =====================================================
    # MODEL PARAMETERS
    # =====================================================

    shortage_penalty = 1000

    # Penalty for excess stock remaining after
    # satisfying the planning requirement.
    wastage_penalty = 8

    # =====================================================
    # DECISION VARIABLES
    # =====================================================

    procurement = {}
    transfer = {}
    shortage = {}
    wastage = {}

    # -----------------------------------------------------
    # Procurement, shortage and wastage variables
    # -----------------------------------------------------

    for item in inventory_data:

        hospital_id = item["hospital_id"]
        resource_id = item["resource_id"]

        key = (hospital_id, resource_id)

        procurement[key] = solver.IntVar(
            0,
            solver.infinity(),
            f"procure_{hospital_id}_{resource_id}"
        )

        shortage[key] = solver.IntVar(
            0,
            solver.infinity(),
            f"shortage_{hospital_id}_{resource_id}"
        )

        wastage[key] = solver.IntVar(
            0,
            solver.infinity(),
            f"wastage_{hospital_id}_{resource_id}"
        )

    # -----------------------------------------------------
    # Inter-hospital transfer variables
    # -----------------------------------------------------

    for source in inventory_data:

        for target in inventory_data:

            # Same hospital → no transfer
            if source["hospital_id"] == target["hospital_id"]:
                continue

            # Different resources → no transfer
            if source["resource_id"] != target["resource_id"]:
                continue

            source_id = source["hospital_id"]
            target_id = target["hospital_id"]
            resource_id = source["resource_id"]

            key = (
                source_id,
                target_id,
                resource_id
            )

            transfer[key] = solver.IntVar(
                0,
                solver.infinity(),
                f"transfer_{source_id}_{target_id}_{resource_id}"
            )

    # =====================================================
    # CONSTRAINTS
    # =====================================================

    for item in inventory_data:

        hospital_id = item["hospital_id"]
        resource_id = item["resource_id"]

        key = (hospital_id, resource_id)

        # -------------------------------------------------
        # Required stock
        # -------------------------------------------------

        required_stock = item["required_stock"]

        # -------------------------------------------------
        # Find incoming and outgoing transfers
        # -------------------------------------------------

        incoming_transfer = []
        outgoing_transfer = []

        for transfer_key in transfer:

            source_id, target_id, res_id = transfer_key

            if res_id != resource_id:
                continue

            # Incoming transfer
            if target_id == hospital_id:
                incoming_transfer.append(
                    transfer[transfer_key]
                )

            # Outgoing transfer
            if source_id == hospital_id:
                outgoing_transfer.append(
                    transfer[transfer_key]
                )

        # -------------------------------------------------
        # Final available stock
        # -------------------------------------------------

        final_stock = (
            item["usable_stock"]
            + procurement[key]
            + solver.Sum(incoming_transfer)
            - solver.Sum(outgoing_transfer)
        )

        # -------------------------------------------------
        # Requirement constraint
        # -------------------------------------------------

        solver.Add(
            final_stock + shortage[key]
            >= required_stock
        )

        # -------------------------------------------------
        # Donor transfer constraint
        # -------------------------------------------------

        transferable_stock = max(
            0,
            item["transferable_stock"]
        )

        solver.Add(
            solver.Sum(outgoing_transfer)
            <= transferable_stock
        )

        # -------------------------------------------------
        # Excess / wastage constraint
        # -------------------------------------------------

        solver.Add(
            wastage[key]
            >= final_stock - required_stock
        )

        solver.Add(
            wastage[key] >= 0
        )

        # -------------------------------------------------
        # Expiry-aware transfer constraint
        # -------------------------------------------------

        if expiry_data:

            expiry_info = expiry_data.get(
                (hospital_id, resource_id),
                {}
            )

            days_until_expiry = expiry_info.get(
                "days_until_expiry",
                9999
            )

            # If the earliest batch expires during
            # the planning horizon, do not allow the
            # optimizer to transfer more than the
            # genuinely transferable surplus.
            if days_until_expiry <= planning_horizon_days:

                safe_transfer_limit = max(
                    0,
                    item["usable_stock"] - required_stock
                )

                solver.Add(
                    solver.Sum(outgoing_transfer)
                    <= safe_transfer_limit
                )

    # =====================================================
    # OBJECTIVE FUNCTION
    # =====================================================

    objective_terms = []

    # -----------------------------------------------------
    # 1. Procurement cost
    # -----------------------------------------------------

    for key, variable in procurement.items():

        resource_id = key[1]

        cost = procurement_costs.get(
            resource_id,
            0
        )

        objective_terms.append(
            cost * variable
        )

    # -----------------------------------------------------
    # 2. Transportation cost
    # -----------------------------------------------------

    for key, variable in transfer.items():

        source_id = key[0]
        target_id = key[1]

        cost = transport_costs.get(
            (source_id, target_id),
            0
        )

        objective_terms.append(
            cost * variable
        )

    # -----------------------------------------------------
    # 3. Shortage penalty
    # -----------------------------------------------------

    for variable in shortage.values():

        objective_terms.append(
            shortage_penalty * variable
        )

    # -----------------------------------------------------
    # 4. Wastage / excess penalty
    # -----------------------------------------------------

    for variable in wastage.values():

        objective_terms.append(
            wastage_penalty * variable
        )

    # -----------------------------------------------------
    # Minimize total objective
    # -----------------------------------------------------

    solver.Minimize(
        solver.Sum(objective_terms)
    )

    # =====================================================
    # SOLVE
    # =====================================================

    status = solver.Solve()

    if status != pywraplp.Solver.OPTIMAL:

        return {
            "status": "NO_OPTIMAL_SOLUTION",
            "procurement": [],
            "redistribution": [],
            "shortage": [],
            "wastage": []
        }

    # =====================================================
    # RESULTS
    # =====================================================

    # -----------------------------------------------------
    # Procurement results
    # -----------------------------------------------------

    procurement_results = []

    for key, variable in procurement.items():

        quantity = variable.solution_value()

        if quantity > 0:

            procurement_results.append({
                "hospital_id": key[0],
                "resource_id": key[1],
                "quantity": int(quantity)
            })

    # -----------------------------------------------------
    # Redistribution results
    # -----------------------------------------------------

    transfer_results = []

    for key, variable in transfer.items():

        quantity = variable.solution_value()

        if quantity > 0:

            transfer_results.append({
                "source_hospital_id": key[0],
                "target_hospital_id": key[1],
                "resource_id": key[2],
                "quantity": int(quantity)
            })

    # -----------------------------------------------------
    # Shortage results
    # -----------------------------------------------------

    shortage_results = []

    for key, variable in shortage.items():

        quantity = variable.solution_value()

        if quantity > 0:

            shortage_results.append({
                "hospital_id": key[0],
                "resource_id": key[1],
                "shortage_quantity": int(quantity)
            })

    # -----------------------------------------------------
    # Wastage / excess results
    # -----------------------------------------------------

    wastage_results = []

    for key, variable in wastage.items():

        quantity = variable.solution_value()

        if quantity > 0:

            wastage_results.append({
                "hospital_id": key[0],
                "resource_id": key[1],
                "wastage_quantity": int(quantity)
            })

    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    return {
        "status": "OPTIMAL",

        "objective_value": round(
            solver.Objective().Value(),
            2
        ),

        "procurement": procurement_results,

        "redistribution": transfer_results,

        "shortage": shortage_results,

        "wastage": wastage_results
    }