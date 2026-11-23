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
    Recommendation,
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
    lead_time_days: int,
    criticality: str = "MEDIUM"
):
    new_resource = Resource(
        resource_name=resource_name,
        category=category,
        unit=unit,
        supplier_id=supplier_id,
        reorder_level=reorder_level,
        safety_stock=safety_stock,
        lead_time_days=lead_time_days,
        criticality=criticality
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
    received_date,
    reserved_quantity: int = 0
):
    try:
        quantity = int(quantity)
        reserved_quantity = int(reserved_quantity)

        if quantity < 0 or reserved_quantity < 0:
            raise ValueError("Batch quantities cannot be negative.")
        if reserved_quantity > quantity:
            raise ValueError("Reserved quantity cannot exceed batch quantity.")

        inventory = (
            db.query(Inventory)
            .filter(Inventory.inventory_id == inventory_id)
            .with_for_update()
            .first()
        )
        if inventory is None:
            raise ValueError("Inventory record not found.")

        new_batch = ResourceBatch(
            inventory_id=inventory_id,
            batch_number=batch_number,
            quantity=quantity,
            reserved_quantity=reserved_quantity,
            manufacturing_date=manufacturing_date,
            expiry_date=expiry_date,
            received_date=received_date
        )
        db.add(new_batch)
        db.flush()

        batches = (
            db.query(ResourceBatch)
            .filter(ResourceBatch.inventory_id == inventory_id)
            .all()
        )
        total_quantity = sum(int(batch.quantity or 0) for batch in batches)
        total_reserved = sum(int(batch.reserved_quantity or 0) for batch in batches)

        inventory.current_quantity = total_quantity
        inventory.reserved_quantity = total_reserved
        inventory.usable_quantity = total_quantity - total_reserved
        inventory.last_updated = datetime.now(timezone.utc)

        db.commit()
        db.refresh(new_batch)
        return new_batch
    except Exception:
        db.rollback()
        raise


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
    try:
        quantity_consumed = int(quantity_consumed)

        if quantity_consumed <= 0:
            raise ValueError(
                "Consumption quantity must be greater than zero."
            )

        # Lock inventory first to serialize stock operations.
        inventory = (
            db.query(Inventory)
            .filter(
                Inventory.hospital_id == hospital_id,
                Inventory.resource_id == resource_id
            )
            .with_for_update()
            .first()
        )

        if inventory is None:
            raise ValueError("Inventory record not found.")

        today = datetime.now(timezone.utc).date()

        # Lock all batches belonging to this inventory.
        batches = (
            db.query(ResourceBatch)
            .filter(
                ResourceBatch.inventory_id == inventory.inventory_id
            )
            .order_by(
                ResourceBatch.expiry_date.asc(),
                ResourceBatch.batch_id.asc()
            )
            .with_for_update()
            .all()
        )

        allocations = []
        remaining = quantity_consumed

        if batches:
            # Batch ledger is authoritative when batches exist.
            eligible_batches = []

            for batch in batches:
                expiry = batch.expiry_date

                if expiry is None:
                    raise ValueError(
                        f"Expiry date missing for batch {batch.batch_id}."
                    )

                if isinstance(expiry, datetime):
                    expiry = expiry.date()

                available = (
                    int(batch.quantity or 0)
                    - int(batch.reserved_quantity or 0)
                )

                if available < 0:
                    raise ValueError(
                        f"Invalid reserved quantity in batch {batch.batch_id}."
                    )

                if expiry >= today and available > 0:
                    eligible_batches.append((batch, available))

            total_available = sum(
                available
                for _, available in eligible_batches
            )

            if total_available < quantity_consumed:
                raise ValueError(
                    f"Insufficient eligible batch stock. "
                    f"Available: {total_available}, "
                    f"requested: {quantity_consumed}."
                )

            # FEFO allocation: earliest expiry first.
            for batch, available in eligible_batches:
                if remaining == 0:
                    break

                used = min(remaining, available)

                batch.quantity = int(batch.quantity) - used
                remaining -= used

                allocations.append({
                    "batch_id": batch.batch_id,
                    "batch_number": batch.batch_number,
                    "quantity_consumed": used,
                    "expiry_date": batch.expiry_date
                })

            # Reconcile inventory totals from the batch ledger.
            total_quantity = sum(
                int(batch.quantity or 0)
                for batch in batches
            )

            total_reserved = sum(
                int(batch.reserved_quantity or 0)
                for batch in batches
            )

            inventory.current_quantity = total_quantity
            inventory.reserved_quantity = total_reserved
            inventory.usable_quantity = (
                total_quantity - total_reserved
            )

        else:
            # Legacy aggregate inventory without batch records.
            available = int(inventory.usable_quantity or 0)

            if available < quantity_consumed:
                raise ValueError(
                    f"Insufficient aggregate stock. "
                    f"Available: {available}, "
                    f"requested: {quantity_consumed}."
                )

            inventory.current_quantity = (
                int(inventory.current_quantity or 0)
                - quantity_consumed
            )

            inventory.usable_quantity = (
                available - quantity_consumed
            )

        inventory.last_updated = datetime.now(timezone.utc)

        new_consumption = ConsumptionHistory(
            hospital_id=hospital_id,
            resource_id=resource_id,
            consumption_date=consumption_date,
            quantity_consumed=quantity_consumed
        )

        db.add(new_consumption)
        db.commit()
        db.refresh(new_consumption)

        return {
            "message": "Consumption recorded successfully",
            "consumption_id": new_consumption.consumption_id,
            "hospital_id": hospital_id,
            "resource_id": resource_id,
            "quantity_consumed": quantity_consumed,
            "batch_allocations": allocations,
            "remaining_quantity": inventory.usable_quantity
        }

    except Exception:
        db.rollback()
        raise



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
    status: str,
    criticality: str = "MEDIUM"
):
    new_equipment = Equipment(
        hospital_id=hospital_id,
        equipment_name=equipment_name,
        equipment_type=equipment_type,
        manufacturer=manufacturer,
        model_number=model_number,
        installation_date=installation_date,
        status=status,
        criticality=criticality
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
    hospital_id: int,
    resource_id: int,
    shortage_risk: float,
    wastage_risk: float,
    risk_level: str,
    expected_stockout_date=None,
    expected_wastage_quantity=None
):
    analysis_date = datetime.now(timezone.utc).date()

    risk = db.query(RiskAnalysis).filter(
        RiskAnalysis.hospital_id == hospital_id,
        RiskAnalysis.resource_id == resource_id,
        RiskAnalysis.analysis_date == analysis_date
    ).first()


    if risk:
        risk.shortage_risk = shortage_risk
        risk.wastage_risk = wastage_risk
        risk.risk_level = risk_level
        risk.expected_stockout_date = expected_stockout_date
        risk.expected_wastage_quantity = expected_wastage_quantity

    else:
        risk = RiskAnalysis(
            hospital_id=hospital_id,
            resource_id=resource_id,
            analysis_date=analysis_date,
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
    planning_horizon_days=7,
    equipment_data=None,
    downtime_penalty_per_hour=1000
):
    """Optimize hospital inventory, procurement, transfers and maintenance.

    Batch-aware mode is enabled when an inventory item contains
    ``consumption_required``. Batch stock excludes reserved and expired units.
    The solver allocates predicted demand across local batches, incoming
    batches, legacy aggregate stock, procurement usage, and unmet demand.
    FEFO is enforced inside the solver for local use, dispatch, and combined
    receiving-hospital consumption.
    """
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        raise RuntimeError("OR-Tools SCIP solver could not be created")

    expiry_data = expiry_data or {}
    procurement_costs = procurement_costs or {}
    transport_costs = transport_costs or {}
    equipment_data = equipment_data or []

    shortage_penalty = 1000
    wastage_penalty = 8
    expiry_penalty = 20

    # ---------------------------------------------------------
    # Normalize batch data and calculate eligible stock.
    # ---------------------------------------------------------
    batches_by_key = {}
    batch_ledger_keys = set()
    stock_by_key = {}
    consumption_mode = {}
    legacy_expiry_days = {}

    for item in inventory_data:
        key = (item["hospital_id"], item["resource_id"])
        raw_batches = expiry_data.get(key, []) or []
        if isinstance(raw_batches, dict):
            raw_batches = [raw_batches]

        normalized = []
        legacy_days = []
        for batch in raw_batches:
            days_left = batch.get("days_until_expiry", 999999)
            days_left = 999999 if days_left is None else int(days_left)
            legacy_days.append(days_left)

            if "batch_id" not in batch:
                continue
            quantity = int(batch.get("quantity", 0))
            reserved = int(batch.get("reserved_quantity", 0))

            if quantity < 0:
                raise ValueError(
                    f"Batch quantity cannot be negative: {key}"
                )

            if reserved < 0:
                raise ValueError(
                    f"Reserved quantity cannot be negative: {key}"
                )

            if reserved > quantity:
                raise ValueError(
                    f"Reserved quantity exceeds batch quantity: {key}"
                )

            expected_available = quantity - reserved

            if batch.get("available_quantity") is not None:
                available = int(batch["available_quantity"])

                if available < 0 or available != expected_available:
                    raise ValueError(
                        f"Invalid available quantity for batch {batch['batch_id']}: "
                        f"expected {expected_available}, received {available}"
                    )
            else:
                available = expected_available

            if days_left < 0:
                available = 0


            normalized.append({
                "batch_id": batch["batch_id"],
                "batch_number": batch.get("batch_number"),
                "expiry_date": batch.get("expiry_date"),
                "days_until_expiry": days_left,
                "quantity": quantity,
                "reserved_quantity": reserved,
                "available_quantity": available,
            })

        normalized.sort(key=lambda b: (
            b["days_until_expiry"],
            str(b["expiry_date"] or ""),
            str(b["batch_id"]),
        ))
        batches_by_key[key] = normalized
        legacy_expiry_days[key] = min(legacy_days, default=999999)

        # A supplied batch ledger is authoritative, including when every
        # batch is expired or fully reserved.
        has_batch_ledger = any("batch_id" in b for b in raw_batches)
        if has_batch_ledger:
            batch_ledger_keys.add(key)
            stock_by_key[key] = sum(b["available_quantity"] for b in normalized)
        else:
            stock_by_key[key] = max(0, int(item.get("usable_stock", 0)))

        consumption_mode[key] = "consumption_required" in item

    # ---------------------------------------------------------
    # Decision variables.
    # ---------------------------------------------------------
    procurement = {}
    transfer = {}
    shortage = {}
    wastage = {}
    maintenance = {}

    for item in inventory_data:
        hospital_id = item["hospital_id"]
        resource_id = item["resource_id"]
        key = (hospital_id, resource_id)

        procurement[key] = solver.IntVar(
            0, solver.infinity(), f"procure_{hospital_id}_{resource_id}"
        )
        shortage[key] = solver.IntVar(
            0, solver.infinity(), f"shortage_{hospital_id}_{resource_id}"
        )
        wastage[key] = solver.IntVar(
            0, solver.infinity(), f"wastage_{hospital_id}_{resource_id}"
        )

        if int(item.get("lead_time_days", 0)) > planning_horizon_days:
            solver.Add(procurement[key] == 0)

        # Do not allow free procurement when no valid supplier price exists.
        if resource_id not in procurement_costs:
            solver.Add(procurement[key] == 0)
        elif float(procurement_costs[resource_id]) < 0:
            raise ValueError(f"Invalid procurement cost for resource {resource_id}")

    for source in inventory_data:
        for target in inventory_data:
            if source["hospital_id"] == target["hospital_id"]:
                continue
            if source["resource_id"] != target["resource_id"]:
                continue
            source_id = source["hospital_id"]
            target_id = target["hospital_id"]
            resource_id = source["resource_id"]
            route_key = (source_id, target_id, resource_id)
            transfer[route_key] = solver.IntVar(
                0, solver.infinity(),
                f"transfer_{source_id}_{target_id}_{resource_id}"
            )

    # ---------------------------------------------------------
    # Batch-level solver decision variables.
    # Batch shipment variables are linked to aggregate route variables below;
    # batch use is linked to the demand-coverage balance below.
    # ---------------------------------------------------------
    batch_consumption = {}
    batch_transfer = {}
    incoming_batch_consumption = {}

    # Consumption from each hospital's own eligible batch.
    for key, batches in batches_by_key.items():
        if not consumption_mode.get(key, False):
            continue
        hospital_id, resource_id = key
        for batch_index, batch in enumerate(batches):
            batch_id = batch["batch_id"]
            available = int(batch["available_quantity"])
            if available <= 0:
                continue

            batch_key = (hospital_id, resource_id, batch_id)
            batch_consumption[batch_key] = solver.IntVar(
                0,
                available,
                f"batch_consume_{hospital_id}_{resource_id}_{batch_index}"
            )

    # Shipment decision for each source batch on each valid hospital route.
    for route_key in transfer:
        source_id, target_id, resource_id = route_key
        source_key = (source_id, resource_id)

        for batch_index, batch in enumerate(batches_by_key.get(source_key, [])):
            available = int(batch["available_quantity"])
            if available <= 0:
                continue

            batch_id = batch["batch_id"]
            batch_route_key = (
                source_id, target_id, resource_id, batch_id
            )
            batch_transfer[batch_route_key] = solver.IntVar(
                0,
                available,
                f"batch_ship_{source_id}_{target_id}_{resource_id}_{batch_index}"
            )

            # Amount of this transferred batch that the receiving hospital
            # will use for its own predicted consumption.
            if consumption_mode.get((target_id, resource_id), False):
                incoming_batch_consumption[batch_route_key] = solver.IntVar(
                    0,
                    available,
                    f"incoming_batch_consume_{source_id}_{target_id}_{resource_id}_{batch_index}"
                )

    # ---------------------------------------------------------
    # Link batch-level shipments to aggregate transfer decisions.
    # ---------------------------------------------------------
    # For a source with an authoritative batch ledger, the aggregate route
    # quantity must equal the sum shipped from its individual batches.
    # This prevents the aggregate model from transferring stock that has no
    # corresponding batch allocation. Legacy aggregate-only sources retain
    # their original aggregate transfer path.
    for route_key, aggregate_transfer_var in transfer.items():
        source_id, target_id, resource_id = route_key
        source_key = (source_id, resource_id)
        if source_key not in batch_ledger_keys:
            continue

        route_batch_vars = [
            variable
            for batch_route_key, variable in batch_transfer.items()
            if batch_route_key[0] == source_id
            and batch_route_key[1] == target_id
            and batch_route_key[2] == resource_id
        ]
        solver.Add(aggregate_transfer_var == solver.Sum(route_batch_vars))

    # ---------------------------------------------------------
    # Batch availability and reserved-stock constraints.
    # ---------------------------------------------------------
    # A batch's usable capacity is quantity minus reserved quantity.
    # Local consumption and all outbound shipments share this same pool;
    # therefore the same physical unit cannot be consumed and dispatched.
    for key, batches in batches_by_key.items():
        hospital_id, resource_id = key
        for batch in batches:
            batch_id = batch["batch_id"]
            batch_key = (hospital_id, resource_id, batch_id)
            available_capacity = max(
                0,
                int(batch["quantity"]) - int(batch["reserved_quantity"])
            )

            local_consumption_var = batch_consumption.get(batch_key)
            if local_consumption_var is None:
                local_consumption_var = 0

            outbound_batch_vars = [
                variable
                for route_batch_key, variable in batch_transfer.items()
                if route_batch_key[0] == hospital_id
                and route_batch_key[2] == resource_id
                and route_batch_key[3] == batch_id
            ]

            solver.Add(
                local_consumption_var + solver.Sum(outbound_batch_vars)
                <= available_capacity
            )

    # A receiving hospital cannot consume more from an incoming batch than
    # the quantity actually shipped on that route.
    for route_batch_key, incoming_use_var in incoming_batch_consumption.items():
        shipped_var = batch_transfer[route_batch_key]
        solver.Add(incoming_use_var <= shipped_var)

    # ---------------------------------------------------------
    # Receiving-hospital consumption across local + inbound batches.
    # ---------------------------------------------------------
    batch_consumption_total = {}
    aggregate_consumption = {}
    procurement_used = {}
    unmet_consumption = {}
    for item in inventory_data:
        target_id = item["hospital_id"]
        resource_id = item["resource_id"]
        key = (target_id, resource_id)
        if not consumption_mode.get(key, False):
            continue

        demand = max(0, int(item.get("consumption_required", 0)))
        local_vars = [
            variable
            for batch_key, variable in batch_consumption.items()
            if batch_key[0] == target_id and batch_key[1] == resource_id
        ]
        inbound_vars = [
            variable
            for route_batch_key, variable in incoming_batch_consumption.items()
            if route_batch_key[1] == target_id and route_batch_key[2] == resource_id
        ]

        total_var = solver.IntVar(
            0, demand,
            f"total_batch_consumption_{target_id}_{resource_id}"
        )
        batch_consumption_total[key] = total_var
        solver.Add(total_var == solver.Sum(local_vars + inbound_vars))
        solver.Add(total_var <= demand)

        # The remaining demand must be covered by legacy aggregate stock,
        # procurement actually used, or explicitly reported as unmet.
        aggregate_use = solver.IntVar(
            0, demand, f"aggregate_consume_{target_id}_{resource_id}"
        )
        purchased_use = solver.IntVar(
            0, demand, f"procurement_use_{target_id}_{resource_id}"
        )
        unmet = solver.IntVar(
            0, demand, f"unmet_consumption_{target_id}_{resource_id}"
        )
        aggregate_consumption[key] = aggregate_use
        procurement_used[key] = purchased_use
        unmet_consumption[key] = unmet

        # Only aggregate-only local inventory and transfers from aggregate-only
        # sources belong in this pool. Batch-ledger stock is accounted for by
        # batch_consumption_total and must not be counted twice.
        aggregate_local = (
            stock_by_key.get(key, 0) if key not in batch_ledger_keys else 0
        )
        aggregate_incoming_vars = [
            variable
            for route_key, variable in transfer.items()
            if route_key[1] == target_id
            and route_key[2] == resource_id
            and (route_key[0], resource_id) not in batch_ledger_keys
        ]
        aggregate_outgoing_vars = [
            variable
            for route_key, variable in transfer.items()
            if route_key[0] == target_id
            and route_key[2] == resource_id
            and key not in batch_ledger_keys
        ]
        aggregate_available = (
            aggregate_local
            + solver.Sum(aggregate_incoming_vars)
            - solver.Sum(aggregate_outgoing_vars)
        )
        solver.Add(aggregate_use <= aggregate_available)
        solver.Add(purchased_use <= procurement[key])
        solver.Add(
            total_var + aggregate_use + purchased_use + unmet == demand
        )

    # ---------------------------------------------------------
    # FEFO priority constraints (solver-enforced).
    # ---------------------------------------------------------
    # If a later-expiring lot is used, every earlier-expiring eligible lot
    # must first be fully used. Binary indicators make this a MILP constraint
    # rather than a Python post-processing allocation.
    fefo_big_m = max(
        1,
        sum(
            int(batch["available_quantity"])
            for batch_list in batches_by_key.values()
            for batch in batch_list
        ),
    )

    # 1) Local consumption FEFO within each hospital/resource.
    for key, batches in batches_by_key.items():
        if not consumption_mode.get(key, False):
            continue
        hospital_id, resource_id = key
        ordered_lots = []
        for batch in batches:
            batch_id = batch["batch_id"]
            batch_key = (hospital_id, resource_id, batch_id)
            use_var = batch_consumption.get(batch_key)
            if use_var is None:
                continue
            outbound_vars = [
                var for route_batch_key, var in batch_transfer.items()
                if route_batch_key[0] == hospital_id
                and route_batch_key[2] == resource_id
                and route_batch_key[3] == batch_id
            ]
            remaining_capacity = (
                int(batch["available_quantity"]) - solver.Sum(outbound_vars)
            )
            ordered_lots.append((batch, use_var, remaining_capacity))

        for later_index in range(1, len(ordered_lots)):
            later_batch, later_use, _later_capacity = ordered_lots[later_index]
            later_used = solver.BoolVar(
                f"fefo_local_used_{hospital_id}_{resource_id}_{later_index}"
            )
            solver.Add(later_use <= fefo_big_m * later_used)
            for earlier_index in range(later_index):
                _earlier_batch, earlier_use, earlier_capacity = ordered_lots[earlier_index]
                solver.Add(
                    earlier_use >= earlier_capacity
                    - fefo_big_m * (1 - later_used)
                )

    # 2) Outgoing dispatch FEFO: earlier batches are dispatched before later
    # batches, after accounting for units consumed locally from each batch.
    for key, batches in batches_by_key.items():
        hospital_id, resource_id = key
        ordered_dispatch = []
        for batch in batches:
            batch_id = batch["batch_id"]
            batch_key = (hospital_id, resource_id, batch_id)
            local_use = batch_consumption.get(batch_key, 0)
            outbound_vars = [
                var for route_batch_key, var in batch_transfer.items()
                if route_batch_key[0] == hospital_id
                and route_batch_key[2] == resource_id
                and route_batch_key[3] == batch_id
            ]
            dispatched = solver.Sum(outbound_vars)
            dispatch_capacity = int(batch["available_quantity"]) - local_use
            if outbound_vars:
                ordered_dispatch.append((batch, dispatched, dispatch_capacity))

        for later_index in range(1, len(ordered_dispatch)):
            later_batch, later_dispatch, _later_capacity = ordered_dispatch[later_index]
            later_used = solver.BoolVar(
                f"fefo_dispatch_used_{hospital_id}_{resource_id}_{later_index}"
            )
            solver.Add(later_dispatch <= fefo_big_m * later_used)
            for earlier_index in range(later_index):
                _earlier_batch, earlier_dispatch, earlier_capacity = ordered_dispatch[earlier_index]
                solver.Add(
                    earlier_dispatch >= earlier_capacity
                    - fefo_big_m * (1 - later_used)
                )

    # 3) Combined receiving FEFO across local batches and inbound batches.
    # A destination consumes the earliest-expiring lot first regardless of
    # whether that lot was already local or arrived through redistribution.
    for item in inventory_data:
        target_id = item["hospital_id"]
        resource_id = item["resource_id"]
        target_key = (target_id, resource_id)
        if not consumption_mode.get(target_key, False):
            continue

        receiving_lots = []
        for batch in batches_by_key.get(target_key, []):
            batch_id = batch["batch_id"]
            batch_key = (target_id, resource_id, batch_id)
            use_var = batch_consumption.get(batch_key)
            if use_var is None:
                continue
            outbound_vars = [
                var for route_batch_key, var in batch_transfer.items()
                if route_batch_key[0] == target_id
                and route_batch_key[2] == resource_id
                and route_batch_key[3] == batch_id
            ]
            capacity = int(batch["available_quantity"]) - solver.Sum(outbound_vars)
            receiving_lots.append((batch, use_var, capacity, "local"))

        for route_batch_key, use_var in incoming_batch_consumption.items():
            source_id, destination_id, route_resource, batch_id = route_batch_key
            if destination_id != target_id or route_resource != resource_id:
                continue
            source_key = (source_id, resource_id)
            source_batch = next(
                (b for b in batches_by_key.get(source_key, []) if b["batch_id"] == batch_id),
                None,
            )
            if source_batch is None:
                continue
            receiving_lots.append((
                source_batch,
                use_var,
                batch_transfer[route_batch_key],
                f"incoming_{source_id}",
            ))

        receiving_lots.sort(key=lambda lot: (
            lot[0]["days_until_expiry"],
            str(lot[0].get("expiry_date") or "9999-12-31"),
            str(lot[0]["batch_id"]),
            lot[3],
        ))

        for later_index in range(1, len(receiving_lots)):
            _later_batch, later_use, _later_capacity, _later_source = receiving_lots[later_index]
            later_used = solver.BoolVar(
                f"fefo_receiving_used_{target_id}_{resource_id}_{later_index}"
            )
            solver.Add(later_use <= fefo_big_m * later_used)
            for earlier_index in range(later_index):
                _earlier_batch, earlier_use, earlier_capacity, _earlier_source = receiving_lots[earlier_index]
                solver.Add(
                    earlier_use >= earlier_capacity
                    - fefo_big_m * (1 - later_used)
                )

    # ---------------------------------------------------------
    # Stock balance and constraints.
    # ---------------------------------------------------------
    for item in inventory_data:
        hospital_id = item["hospital_id"]
        resource_id = item["resource_id"]
        key = (hospital_id, resource_id)
        incoming = []
        outgoing = []

        for route_key, variable in transfer.items():
            source_id, target_id, route_resource = route_key
            if route_resource != resource_id:
                continue
            if target_id == hospital_id:
                incoming.append(variable)
            if source_id == hospital_id:
                outgoing.append(variable)

        usable_stock = stock_by_key[key]

        if consumption_mode[key]:
            consumption = max(0, int(item.get("consumption_required", 0)))
            safety_stock = max(0, int(item.get("safety_stock", 0)))
            final_stock = (
                usable_stock + procurement[key] + solver.Sum(incoming)
                - solver.Sum(outgoing) - consumption
            )
            required_end_stock = safety_stock
            transferable_limit = max(0, usable_stock - consumption - safety_stock)
        else:
            final_stock = (
                usable_stock + procurement[key] + solver.Sum(incoming)
                - solver.Sum(outgoing)
            )
            required_end_stock = max(0, int(item.get("required_stock", 0)))
            transferable_limit = max(0, int(item.get("transferable_stock", 0)))

        solver.Add(final_stock + shortage[key] >= required_end_stock)
        # For demand-driven inventory, shortage must never under-report the
        # demand that the solver explicitly leaves unmet. The stock-balance
        # constraint may require a larger shortage when safety stock is also
        # unavailable.
        if consumption_mode[key] and key in unmet_consumption:
            solver.Add(shortage[key] >= unmet_consumption[key])
        solver.Add(solver.Sum(outgoing) <= transferable_limit)
        solver.Add(solver.Sum(outgoing) <= usable_stock)
        solver.Add(wastage[key] >= final_stock - required_end_stock)
        solver.Add(wastage[key] >= 0)

        earliest_days = min(
            legacy_expiry_days.get(key, 999999),
            min((b["days_until_expiry"] for b in batches_by_key.get(key, [])), default=999999),
        )
        if earliest_days <= planning_horizon_days:
            solver.Add(solver.Sum(outgoing) <= transferable_limit)

    # ---------------------------------------------------------
    # Route validation and maintenance variables.
    # ---------------------------------------------------------
    for route_key, variable in transfer.items():
        source_id, target_id, _resource_id = route_key
        route = (source_id, target_id)
        if route not in transport_costs:
            solver.Add(variable == 0)
            continue
        if float(transport_costs[route]) < 0:
            raise ValueError(f"Invalid transportation cost for route {route}")

    for equipment in equipment_data:
        equipment_id = equipment["equipment_id"]
        maintenance[equipment_id] = solver.IntVar(0, 1, f"maintenance_{equipment_id}")


    # ---------------------------------------------------------
    # Objective.
    # ---------------------------------------------------------
    objective_terms = []

    for key, variable in procurement.items():
        price = procurement_costs.get(key[1])
        if price is not None:
            objective_terms.append(float(price) * variable)

    for route_key, variable in transfer.items():
        source_id, target_id, _resource_id = route_key
        route_price = transport_costs.get((source_id, target_id))
        if route_price is not None:
            objective_terms.append(float(route_price) * variable)

    objective_terms.extend(
        shortage_penalty * v for v in shortage.values()
    )
    objective_terms.extend(
        wastage_penalty * v for v in wastage.values()
    )

    # Expiry penalty.
    for item in inventory_data:
        key = (item["hospital_id"], item["resource_id"])

        earliest_days = min(
            legacy_expiry_days.get(key, 999999),
            min(
                (
                    b["days_until_expiry"]
                    for b in batches_by_key.get(key, [])
                ),
                default=999999,
            ),
        )

        if earliest_days <= planning_horizon_days:
            objective_terms.append(expiry_penalty * wastage[key])

    # Maintenance objective — independent of inventory.
    criticality_multipliers = {
        "URGENT": 4.0,
        "HIGH": 3.0,
        "MEDIUM": 2.0,
        "LOW": 1.0,
    }

    for equipment in equipment_data:
        equipment_id = equipment["equipment_id"]

        maintenance_cost = float(
            equipment.get("maintenance_cost", 0) or 0
        )
        downtime_hours = float(
            equipment.get("avoidable_downtime_hours", 0) or 0
        )

        criticality = str(
            equipment.get("criticality", "MEDIUM")
        ).upper().strip()

        if criticality not in criticality_multipliers:
            raise ValueError(
                f"Invalid equipment criticality: {criticality}"
            )

        multiplier = criticality_multipliers[criticality]
        decision = maintenance[equipment_id]

        weighted_downtime_penalty = (
            downtime_penalty_per_hour * multiplier * downtime_hours
        )

        objective_terms.append(
            maintenance_cost * decision
            + weighted_downtime_penalty * (1 - decision)
        )

    # Prefer consuming traceable batches (including inbound batches) when
    # doing so does not change any material procurement/transfer decision.
    # The tiny tie-break coefficient is intentionally much smaller than the
    # business penalties and costs in the primary objective.
    objective_terms.extend(-0.001 * v for v in batch_consumption_total.values())
    # When the aggregate stock-balance objective is indifferent, prefer using
    # available legacy aggregate stock instead of leaving it falsely reported
    # as unmet demand. This is only a tie-breaker, not a business cost.
    objective_terms.extend(-0.001 * v for v in aggregate_consumption.values())
    objective_terms.extend(-0.000001 * v for v in procurement_used.values())

    solver.Minimize(solver.Sum(objective_terms))
    status = solver.Solve()


    if status != pywraplp.Solver.OPTIMAL:
        return {
            "status": "NO_OPTIMAL_SOLUTION",
            "procurement": [], "redistribution": [], "shortage": [],
            "wastage": [], "maintenance": [],
            "batch_consumption": [], "batch_transfers": [],
            "consumption_coverage": [], "unallocated_consumption": [],
        }

    # ---------------------------------------------------------
    # Aggregate solver results.
    # ---------------------------------------------------------
    procurement_results = []
    for key, variable in procurement.items():
        quantity = int(round(variable.solution_value()))
        if quantity > 0:
            procurement_results.append({
                "hospital_id": key[0], "resource_id": key[1],
                "quantity": quantity,
                "reason": "Procurement required after available inventory and redistribution are considered.",
            })

    transfer_results = []
    for route_key, variable in transfer.items():
        quantity = int(round(variable.solution_value()))
        if quantity > 0:
            transfer_results.append({
                "source_hospital_id": route_key[0],
                "target_hospital_id": route_key[1],
                "resource_id": route_key[2],
                "quantity": quantity,
                "reason": "Redistribute eligible surplus stock using FEFO batch allocation.",
            })

    shortage_results = []
    for key, variable in shortage.items():
        quantity = int(round(variable.solution_value()))
        if quantity > 0:
            shortage_results.append({
                "hospital_id": key[0], "resource_id": key[1],
                "shortage_quantity": quantity,
                "reason": "Required ending stock could not be fully satisfied.",
            })

    wastage_results = []
    for key, variable in wastage.items():
        quantity = int(round(variable.solution_value()))
        if quantity > 0:
            wastage_results.append({
                "hospital_id": key[0], "resource_id": key[1],
                "excess_quantity": quantity,
                "note": "Projected excess after the planning requirement; not necessarily expired stock.",
            })

    # ---------------------------------------------------------
    # Batch transfer and consumption results come directly from solver
    # decisions. No Python-side FEFO allocation is performed here.
    # ---------------------------------------------------------
    batch_transfer_results = []
    for route_batch_key, variable in batch_transfer.items():
        quantity = int(round(variable.solution_value()))
        if quantity <= 0:
            continue
        source_id, target_id, resource_id, batch_id = route_batch_key
        source_key = (source_id, resource_id)
        batch = next(
            (b for b in batches_by_key.get(source_key, []) if b["batch_id"] == batch_id),
            None,
        )
        if batch is None:
            continue
        batch_transfer_results.append({
            "source_hospital_id": source_id,
            "target_hospital_id": target_id,
            "resource_id": resource_id,
            "batch_id": batch_id,
            "batch_number": batch.get("batch_number"),
            "quantity": quantity,
            "expiry_date": batch.get("expiry_date"),
            "days_until_expiry": batch.get("days_until_expiry"),
        })

    allocations_by_route = {}
    for lot in batch_transfer_results:
        route_key = (
            lot["source_hospital_id"],
            lot["target_hospital_id"],
            lot["resource_id"],
        )
        allocations_by_route.setdefault(route_key, []).append({
            "batch_id": lot["batch_id"],
            "batch_number": lot["batch_number"],
            "quantity": lot["quantity"],
            "expiry_date": lot["expiry_date"],
            "days_until_expiry": lot["days_until_expiry"],
        })
    for transfer_result in transfer_results:
        route_key = (
            transfer_result["source_hospital_id"],
            transfer_result["target_hospital_id"],
            transfer_result["resource_id"],
        )
        # Keep a stable response schema for both batch-ledger and legacy
        # aggregate-only routes. Legacy routes have no fabricated batch lots.
        transfer_result["batch_allocations"] = allocations_by_route.get(route_key, [])

    batch_consumption_results = []
    for batch_key, variable in batch_consumption.items():
        quantity = int(round(variable.solution_value()))
        if quantity <= 0:
            continue
        hospital_id, resource_id, batch_id = batch_key
        batch = next(
            (b for b in batches_by_key.get((hospital_id, resource_id), [])
             if b["batch_id"] == batch_id),
            None,
        )
        if batch is None:
            continue
        batch_consumption_results.append({
            "hospital_id": hospital_id,
            "resource_id": resource_id,
            "batch_id": batch_id,
            "batch_number": batch.get("batch_number"),
            "quantity": quantity,
            "expiry_date": batch.get("expiry_date"),
            "days_until_expiry": batch.get("days_until_expiry", 999999),
            "source": "local_batch",
        })

    for route_batch_key, variable in incoming_batch_consumption.items():
        quantity = int(round(variable.solution_value()))
        if quantity <= 0:
            continue
        source_id, target_id, resource_id, batch_id = route_batch_key
        source_batch = next(
            (b for b in batches_by_key.get((source_id, resource_id), [])
             if b["batch_id"] == batch_id),
            None,
        )
        if source_batch is None:
            continue
        batch_consumption_results.append({
            "hospital_id": target_id,
            "resource_id": resource_id,
            "batch_id": batch_id,
            "batch_number": source_batch.get("batch_number"),
            "quantity": quantity,
            "expiry_date": source_batch.get("expiry_date"),
            "days_until_expiry": source_batch.get("days_until_expiry", 999999),
            "source": "incoming_transfer",
            "source_hospital_id": source_id,
        })

    # Return allocations in the same FEFO order enforced by the solver.
    batch_consumption_results.sort(key=lambda result: (
        int(result.get("days_until_expiry", 999999)),
        str(result.get("expiry_date") or "9999-12-31"),
        str(result.get("batch_id")),
        0 if result.get("source") == "local_batch" else 1,
    ))

    unallocated_consumption_results = []
    consumption_coverage_results = []
    for item in inventory_data:
        key = (item["hospital_id"], item["resource_id"])
        if not consumption_mode.get(key, False):
            continue

        demand = max(0, int(item.get("consumption_required", 0)))
        batch_used = int(round(batch_consumption_total[key].solution_value()))
        aggregate_used = int(round(aggregate_consumption[key].solution_value()))
        purchased_used = int(round(procurement_used[key].solution_value()))
        unmet_quantity = int(round(unmet_consumption[key].solution_value()))
        purchased_quantity = int(round(procurement[key].solution_value()))

        consumption_coverage_results.append({
            "hospital_id": key[0],
            "resource_id": key[1],
            "demand_quantity": demand,
            "batch_consumed_quantity": batch_used,
            "aggregate_consumed_quantity": aggregate_used,
            "procurement_used_quantity": purchased_used,
            "procurement_purchased_quantity": purchased_quantity,
            "unmet_quantity": unmet_quantity,
        })

        if unmet_quantity > 0:
            unallocated_consumption_results.append({
                "hospital_id": key[0],
                "resource_id": key[1],
                "unallocated_quantity": unmet_quantity,
                "reason": (
                    "Predicted consumption exceeds eligible local, incoming "
                    "and procured stock."
                ),
            })

    # ---------------------------------------------------------
    # Maintenance results.
    # ---------------------------------------------------------
    maintenance_results = []

    criticality_multipliers = {
        "URGENT": 4.0,
        "HIGH": 3.0,
        "MEDIUM": 2.0,
        "LOW": 1.0,
    }

    for equipment in equipment_data:
        equipment_id = equipment["equipment_id"]

        criticality = str(
            equipment.get("criticality", "MEDIUM")
        ).upper().strip()

        multiplier = criticality_multipliers[criticality]

        maintenance_cost = float(
            equipment.get("maintenance_cost", 0) or 0
        )

        downtime_hours = float(
            equipment.get("avoidable_downtime_hours", 0) or 0
        )

        weighted_downtime_penalty = (
            downtime_penalty_per_hour
            * multiplier
            * downtime_hours
        )

        decision_value = maintenance[equipment_id].solution_value()

        if decision_value > 0.5:
            maintenance_results.append({
                "equipment_id": equipment_id,
                "hospital_id": equipment["hospital_id"],
                "criticality": criticality,
                "action": "SCHEDULE_MAINTENANCE",
                "maintenance_cost": round(maintenance_cost, 2),
                "historical_avoidable_downtime_hours": downtime_hours,
                "criticality_multiplier": multiplier,
                "weighted_downtime_penalty": round(
                    weighted_downtime_penalty, 2
                ),
                "reason": (
                    f"Maintenance selected for {criticality}-criticality "
                    "equipment based on the optimization objective."
                ),
            })


    return {
        "status": "OPTIMAL",
        "objective_value": round(solver.Objective().Value(), 2),
        "procurement": procurement_results,
        "redistribution": transfer_results,
        "shortage": shortage_results,
        "wastage": wastage_results,
        "maintenance": maintenance_results,
        "batch_consumption": batch_consumption_results,
        "batch_transfers": batch_transfer_results,
        "consumption_coverage": consumption_coverage_results,
        "unallocated_consumption": unallocated_consumption_results,
    }


def reconcile_inventory_from_batches(db, inventory):
    """Recalculate aggregate inventory from its authoritative batch ledger."""
    batches = (
        db.query(ResourceBatch)
        .filter(ResourceBatch.inventory_id == inventory.inventory_id)
        .all()
    )

    if not batches:
        return

    total = sum(int(batch.quantity or 0) for batch in batches)
    reserved = sum(int(batch.reserved_quantity or 0) for batch in batches)

    if reserved > total:
        raise ValueError("Batch reserved stock exceeds total stock.")

    inventory.current_quantity = total
    inventory.reserved_quantity = reserved
    inventory.usable_quantity = total - reserved
    inventory.last_updated = datetime.now(timezone.utc)


def approve_source_redistribution(db, recommendation_id, source_hospital_id):
    """Record source-hospital authorization. Does not move stock."""
    try:
        recommendation = (
            db.query(Recommendation)
            .filter(
                Recommendation.recommendation_id == recommendation_id
            )
            .with_for_update()
            .first()
        )

        if recommendation is None:
            raise ValueError("Recommendation not found.")

        if recommendation.recommendation_type != "REDISTRIBUTION":
            raise ValueError("This is not a redistribution recommendation.")

        if recommendation.source_hospital_id != source_hospital_id:
            raise ValueError("Only the source hospital can authorize dispatch.")

        if recommendation.status != "PENDING":
            raise ValueError("Recommendation is not pending source approval.")

        recommendation.status = "SOURCE_APPROVED"
        db.commit()
        db.refresh(recommendation)
        return recommendation

    except Exception:
        db.rollback()
        raise


def execute_approved_redistribution(db, recommendation):
    """
    Execute a redistribution after source approval and receiving-hospital
    approval. Both inventory updates occur in the same transaction.
    """
    try:
        if recommendation.recommendation_type != "REDISTRIBUTION":
            raise ValueError("Not a redistribution recommendation.")

        if recommendation.status != "SOURCE_APPROVED":
            raise ValueError("Source-hospital approval is required first.")

        source_id = recommendation.source_hospital_id
        target_id = recommendation.target_hospital_id
        resource_id = recommendation.resource_id

        quantity_value = float(recommendation.recommended_quantity)
        if not quantity_value.is_integer() or quantity_value <= 0:
            raise ValueError("Transfer quantity must be a positive whole number.")

        quantity = int(quantity_value)

        if source_id == target_id:
            raise ValueError("Source and destination hospitals must differ.")

        source = (
            db.query(Inventory)
            .filter(
                Inventory.hospital_id == source_id,
                Inventory.resource_id == resource_id,
            )
            .with_for_update()
            .first()
        )

        if source is None:
            raise ValueError("Source inventory record not found.")

        target = (
            db.query(Inventory)
            .filter(
                Inventory.hospital_id == target_id,
                Inventory.resource_id == resource_id,
            )
            .with_for_update()
            .first()
        )

        source_batches = (
            db.query(ResourceBatch)
            .filter(ResourceBatch.inventory_id == source.inventory_id)
            .order_by(ResourceBatch.expiry_date, ResourceBatch.batch_id)
            .with_for_update()
            .all()
        )

        target_batches = []
        if target is not None:
            target_batches = (
                db.query(ResourceBatch)
                .filter(ResourceBatch.inventory_id == target.inventory_id)
                .with_for_update()
                .all()
            )

        # Create destination inventory if it does not exist.
        if target is None:
            target = Inventory(
                hospital_id=target_id,
                resource_id=resource_id,
                current_quantity=0,
                reserved_quantity=0,
                usable_quantity=0,
                last_updated=datetime.now(timezone.utc),
            )
            db.add(target)
            db.flush()

        today = datetime.now(timezone.utc).date()

        if source_batches:
            # Never mix untraceable aggregate destination stock with
            # newly transferred batches.
            if not target_batches and (
                int(target.current_quantity or 0) != 0
                or int(target.reserved_quantity or 0) != 0
            ):
                raise ValueError(
                    "Destination has aggregate-only stock. "
                    "Reconcile it into batches before receiving batch transfers."
                )

            remaining = quantity
            allocations = []

            for batch in source_batches:
                expiry = batch.expiry_date

                if expiry is None:
                    raise ValueError(
                        f"Source batch {batch.batch_id} has no expiry date."
                    )

                available = (
                    int(batch.quantity or 0)
                    - int(batch.reserved_quantity or 0)
                )

                if available < 0:
                    raise ValueError("Invalid reserved quantity in source batch.")

                if expiry < today or available <= 0:
                    continue

                moved = min(remaining, available)

                if moved <= 0:
                    continue

                batch.quantity = int(batch.quantity) - moved

                # Preserve the original batch identity and expiry information.
                db.add(ResourceBatch(
                    inventory_id=target.inventory_id,
                    batch_number=batch.batch_number,
                    quantity=moved,
                    reserved_quantity=0,
                    manufacturing_date=batch.manufacturing_date,
                    expiry_date=batch.expiry_date,
                    received_date=today,
                ))

                allocations.append({
                    "source_batch_id": batch.batch_id,
                    "batch_number": batch.batch_number,
                    "quantity": moved,
                    "expiry_date": batch.expiry_date,
                })

                remaining -= moved

                if remaining == 0:
                    break

            if remaining:
                raise ValueError(
                    f"Insufficient eligible source batch stock. "
                    f"Short by {remaining} units."
                )

            db.flush()
            reconcile_inventory_from_batches(db, source)
            reconcile_inventory_from_batches(db, target)

        else:
            # Aggregate-only stock can move only to an aggregate-only target.
            if target_batches:
                raise ValueError(
                    "Cannot transfer aggregate-only stock into a batch-ledger inventory."
                )

            available = int(source.usable_quantity or 0)

            if available < quantity:
                raise ValueError(
                    f"Insufficient source stock. Available: {available}."
                )

            source.current_quantity = int(source.current_quantity) - quantity
            source.usable_quantity = available - quantity

            target.current_quantity = (
                int(target.current_quantity or 0) + quantity
            )
            target.usable_quantity = (
                int(target.usable_quantity or 0) + quantity
            )

            source.last_updated = datetime.now(timezone.utc)
            target.last_updated = datetime.now(timezone.utc)
            allocations = []

        recommendation.status = "EXECUTED"
        db.commit()

        return {
            "message": "Redistribution executed successfully.",
            "recommendation_id": recommendation.recommendation_id,
            "source_hospital_id": source_id,
            "target_hospital_id": target_id,
            "resource_id": resource_id,
            "quantity_transferred": quantity,
            "batch_allocations": allocations,
            "status": recommendation.status,
        }

    except Exception:
        db.rollback()
        raise


def receive_procurement(
    db,
    recommendation_id,
    hospital_id,
    batch_number,
    expiry_date,
    manufacturing_date=None,
    received_date=None,
):
    """Record an approved procurement receipt as a new inventory batch."""
    try:
        recommendation = (
            db.query(Recommendation)
            .filter(
                Recommendation.recommendation_id == recommendation_id
            )
            .with_for_update()
            .first()
        )

        if recommendation is None:
            raise ValueError("Recommendation not found.")

        if recommendation.recommendation_type != "PROCUREMENT":
            raise ValueError("This is not a procurement recommendation.")

        if recommendation.hospital_id != hospital_id:
            raise ValueError("Procurement belongs to another hospital.")

        if recommendation.status != "APPROVED":
            raise ValueError("Procurement must be approved before receipt.")

        quantity_value = float(recommendation.recommended_quantity)
        if not quantity_value.is_integer() or quantity_value <= 0:
            raise ValueError("Approved procurement quantity is invalid.")

        quantity = int(quantity_value)

        today = datetime.now(timezone.utc).date()
        received_date = received_date or today

        if expiry_date < today:
            raise ValueError("Cannot receive an already-expired batch.")

        resource_id = recommendation.resource_id

        inventory = (
            db.query(Inventory)
            .filter(
                Inventory.hospital_id == hospital_id,
                Inventory.resource_id == resource_id,
            )
            .with_for_update()
            .first()
        )

        if inventory is None:
            inventory = Inventory(
                hospital_id=hospital_id,
                resource_id=resource_id,
                current_quantity=0,
                reserved_quantity=0,
                usable_quantity=0,
                last_updated=datetime.now(timezone.utc),
            )
            db.add(inventory)
            db.flush()

        # Do not silently combine untracked aggregate stock with a new batch.
        existing_batches = (
            db.query(ResourceBatch)
            .filter(ResourceBatch.inventory_id == inventory.inventory_id)
            .count()
        )

        if existing_batches == 0 and (
            int(inventory.current_quantity or 0) != 0
            or int(inventory.reserved_quantity or 0) != 0
        ):
            raise ValueError(
                "Inventory contains aggregate-only stock. "
                "Reconcile it into batches before receiving procurement."
            )

        batch = ResourceBatch(
            inventory_id=inventory.inventory_id,
            batch_number=batch_number,
            quantity=quantity,
            reserved_quantity=0,
            manufacturing_date=manufacturing_date,
            expiry_date=expiry_date,
            received_date=received_date,
        )

        db.add(batch)
        db.flush()

        reconcile_inventory_from_batches(db, inventory)

        recommendation.status = "RECEIVED"
        db.commit()
        db.refresh(batch)

        return {
            "message": "Procurement receipt recorded successfully.",
            "recommendation_id": recommendation_id,
            "batch_id": batch.batch_id,
            "inventory_id": inventory.inventory_id,
            "quantity_received": quantity,
            "status": recommendation.status,
        }

    except Exception:
        db.rollback()
        raise
