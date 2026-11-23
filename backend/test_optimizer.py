
from services.entity_service import optimize_resource_allocation


def run_test(name, test_function):
    print(f"\n{'=' * 55}")
    print(f"Running: {name}")
    print("=" * 55)

    test_function()

    print(f"PASSED: {name}")


# --------------------------------------------------
# TEST 1: EXPIRY / EXCESS STOCK
# --------------------------------------------------

def test_expiry_optimizer():
    inventory_data = [
        {
            "hospital_id": 99,
            "resource_id": 99,
            "usable_stock": 100,
            "required_stock": 50,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    expiry_data = {
        (99, 99): {
            "expiry_date": "2026-11-21",
            "days_until_expiry": 5,
            "batch_quantity": 100
        }
    }

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={(99, 99): 0},
        procurement_costs={99: 10},
        transport_costs={},
        expiry_data=expiry_data,
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"
    assert isinstance(result["wastage"], list)

    print("Wastage:", result["wastage"])


# --------------------------------------------------
# TEST 2: PROCUREMENT AND REDISTRIBUTION
# --------------------------------------------------

def test_procurement_optimizer():
    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 20,
            "required_stock": 100,
            "transferable_stock": 0,
            "lead_time_days": 0
        },
        {
            "hospital_id": 2,
            "resource_id": 3,
            "usable_stock": 150,
            "required_stock": 100,
            "transferable_stock": 50,
            "lead_time_days": 0
        }
    ]

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={(1, 3): 0, (2, 3): 0},
        procurement_costs={3: 100},
        transport_costs={(2, 1): 5},
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"
    assert isinstance(result["procurement"], list)
    assert isinstance(result["redistribution"], list)

    print("Procurement:", result["procurement"])
    print("Redistribution:", result["redistribution"])


# --------------------------------------------------
# TEST 3: FEFO WITH INCOMING TRANSFER
# --------------------------------------------------

def test_fefo_incoming_transfer():
    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 100,
            "consumption_required": 0,
            "safety_stock": 0,
            "lead_time_days": 7
        },
        {
            "hospital_id": 2,
            "resource_id": 3,
            "usable_stock": 20,
            "consumption_required": 80,
            "safety_stock": 0,
            "lead_time_days": 7
        }
    ]

    expiry_data = {
        (1, 3): [
            {
                "batch_id": 101,
                "batch_number": "INCOMING-EARLY",
                "quantity": 100,
                "reserved_quantity": 0,
                "available_quantity": 100,
                "expiry_date": "2027-01-01",
                "days_until_expiry": 46
            }
        ],
        (2, 3): [
            {
                "batch_id": 102,
                "batch_number": "LOCAL-LATE",
                "quantity": 20,
                "reserved_quantity": 0,
                "available_quantity": 20,
                "expiry_date": "2027-10-01",
                "days_until_expiry": 319
            }
        ]
    }

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={},
        transport_costs={(1, 2): 1},
        expiry_data=expiry_data,
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"

    transfers = result["batch_transfers"]
    consumption = result["batch_consumption"]

    assert sum(x["quantity"] for x in transfers) == 60

    assert [
        (x["batch_id"], x["quantity"])
        for x in consumption
    ] == [
        (101, 60),
        (102, 20)
    ]

    print("Transfers:", transfers)
    print("Consumption:", consumption)


# --------------------------------------------------
# TEST 4: FEFO ACROSS MULTIPLE BATCHES
# --------------------------------------------------

def test_fefo_multiple_batches():
    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 150,
            "consumption_required": 100,
            "safety_stock": 0,
            "lead_time_days": 0
        }
    ]

    expiry_data = {
        (1, 3): [
            {
                "batch_id": 103,
                "batch_number": "BATCH-LATE",
                "quantity": 50,
                "reserved_quantity": 0,
                "available_quantity": 50,
                "expiry_date": "2027-06-01",
                "days_until_expiry": 197
            },
            {
                "batch_id": 101,
                "batch_number": "BATCH-EARLY",
                "quantity": 40,
                "reserved_quantity": 0,
                "available_quantity": 40,
                "expiry_date": "2027-01-01",
                "days_until_expiry": 46
            },
            {
                "batch_id": 102,
                "batch_number": "BATCH-MIDDLE",
                "quantity": 60,
                "reserved_quantity": 0,
                "available_quantity": 60,
                "expiry_date": "2027-03-01",
                "days_until_expiry": 105
            }
        ]
    }

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={},
        transport_costs={},
        expiry_data=expiry_data,
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"

    consumption = result["batch_consumption"]

    assert [
        (x["batch_id"], x["quantity"])
        for x in consumption
    ] == [
        (101, 40),
        (102, 60)
    ]

    assert sum(x["quantity"] for x in consumption) == 100

    print("Consumption:", consumption)


# --------------------------------------------------
# TEST 5: RESERVED STOCK PROTECTION
# --------------------------------------------------

def test_reserved_stock_protection():
    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 60,
            "consumption_required": 0,
            "safety_stock": 0,
            "transferable_stock": 60,
            "lead_time_days": 0
        },
        {
            "hospital_id": 2,
            "resource_id": 3,
            "usable_stock": 0,
            "consumption_required": 50,
            "safety_stock": 0,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    expiry_data = {
        (1, 3): [
            {
                "batch_id": 201,
                "batch_number": "RESERVED-TEST",
                "quantity": 100,
                "reserved_quantity": 40,
                "available_quantity": 60,
                "expiry_date": "2027-06-01",
                "days_until_expiry": 197
            }
        ]
    }

    result = optimize_resource_allocation(
    inventory_data=inventory_data,
    demand_data={},
    procurement_costs={},
    transport_costs={(1, 2): 1},
    expiry_data=expiry_data,
    planning_horizon_days=7,
    equipment_data=[]
)

    assert result["status"] == "OPTIMAL"

    transfers = result["batch_transfers"]

    transferred_quantity = sum(
        item["quantity"] for item in transfers
    )

    assert transferred_quantity <= 60

    print("Batch transfers:", transfers)
    print("Total transferred:", transferred_quantity)



# --------------------------------------------------
# TEST 6: EXPIRED-BATCH EXCLUSION
# --------------------------------------------------

def test_expired_batch_exclusion():
    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 100,
            "consumption_required": 50,
            "safety_stock": 0,
            "transferable_stock": 100,
            "lead_time_days": 0
        }
    ]

    expiry_data = {
        (1, 3): [
            {
                "batch_id": 301,
                "batch_number": "EXPIRED-BATCH",
                "quantity": 100,
                "reserved_quantity": 0,
                "available_quantity": 100,
                "expiry_date": "2026-11-15",
                "days_until_expiry": -1
            }
        ]
    }

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={},
        transport_costs={},
        expiry_data=expiry_data,
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"

    consumption = result["batch_consumption"]
    transfers = result["batch_transfers"]

    expired_batch_used = any(
        item["batch_id"] == 301
        for item in consumption + transfers
    )

    assert not expired_batch_used, (
        "Expired batch was incorrectly allocated!"
    )

    print("Consumption:", consumption)
    print("Transfers:", transfers)
    print("Expired batch correctly excluded.")



# --------------------------------------------------
# TEST 7: INSUFFICIENT STOCK
# --------------------------------------------------

def test_insufficient_stock():
    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 30,
            "required_stock": 100,
            "consumption_required": 100,
            "safety_stock": 0,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    expiry_data = {
        (1, 3): [
            {
                "batch_id": 401,
                "batch_number": "LIMITED-STOCK",
                "quantity": 30,
                "reserved_quantity": 0,
                "available_quantity": 30,
                "expiry_date": "2027-06-01",
                "days_until_expiry": 197
            }
        ]
    }

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={},
        transport_costs={},
        expiry_data=expiry_data,
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"

    consumption = result["batch_consumption"]
    shortage = result["shortage"]

    allocated = sum(
        item["quantity"] for item in consumption
    )

    shortage_quantity = sum(
    item["shortage_quantity"] for item in shortage
    )

    print("Consumption:", consumption)
    print("Shortage:", shortage)

    assert allocated <= 30
    assert allocated + shortage_quantity == 100

    print("Insufficient stock handled correctly.")



# --------------------------------------------------
# TEST 8: ZERO-STOCK AND ZERO-DEMAND
# --------------------------------------------------

def test_zero_stock_and_zero_demand():

    # Scenario A: Zero stock, but demand is 50
    zero_stock_inventory = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 0,
            "consumption_required": 50,
            "required_stock": 50,
            "safety_stock": 0,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    result_a = optimize_resource_allocation(
        inventory_data=zero_stock_inventory,
        demand_data={},
        procurement_costs={},
        transport_costs={},
        expiry_data={(1, 3): []},
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result_a["status"] == "OPTIMAL"

    shortage_a = sum(
        item["shortage_quantity"]
        for item in result_a["shortage"]
    )

    assert shortage_a == 50

    # Scenario B: Stock is 100, but demand is zero
    zero_demand_inventory = [
        {
            "hospital_id": 2,
            "resource_id": 3,
            "usable_stock": 100,
            "consumption_required": 0,
            "required_stock": 0,
            "safety_stock": 0,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    expiry_data_b = {
        (2, 3): [
            {
                "batch_id": 501,
                "batch_number": "ZERO-DEMAND",
                "quantity": 100,
                "reserved_quantity": 0,
                "available_quantity": 100,
                "expiry_date": "2027-06-01",
                "days_until_expiry": 197
            }
        ]
    }

    result_b = optimize_resource_allocation(
        inventory_data=zero_demand_inventory,
        demand_data={},
        procurement_costs={},
        transport_costs={},
        expiry_data=expiry_data_b,
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result_b["status"] == "OPTIMAL"
    assert result_b["shortage"] == []
    assert result_b["batch_consumption"] == []

    print("Scenario A - Zero stock shortage:", shortage_a)
    print("Scenario B - Zero demand consumption:",
          result_b["batch_consumption"])


# --------------------------------------------------
# TEST 9: INVALID BATCH DATA VALIDATION
# --------------------------------------------------

def test_invalid_batch_data():

    base_inventory = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 50,
            "consumption_required": 0,
            "safety_stock": 0,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    invalid_batches = [
        {
            "batch_id": 601,
            "batch_number": "RESERVED-INVALID",
            "quantity": 50,
            "reserved_quantity": 60,
            "available_quantity": 0,
            "expiry_date": "2027-06-01",
            "days_until_expiry": 197
        },
        {
            "batch_id": 602,
            "batch_number": "NEGATIVE-QUANTITY",
            "quantity": -10,
            "reserved_quantity": 0,
            "available_quantity": 0,
            "expiry_date": "2027-06-01",
            "days_until_expiry": 197
        },
        {
            "batch_id": 603,
            "batch_number": "EXCESS-AVAILABLE",
            "quantity": 50,
            "reserved_quantity": 20,
            "available_quantity": 40,
            "expiry_date": "2027-06-01",
            "days_until_expiry": 197
        }
    ]

    for batch in invalid_batches:
        try:
            optimize_resource_allocation(
                inventory_data=base_inventory,
                demand_data={},
                procurement_costs={},
                transport_costs={},
                expiry_data={(1, 3): [batch]},
                planning_horizon_days=7,
                equipment_data=[]
            )

        except ValueError:
            print(
                f"Correctly rejected: {batch['batch_number']}"
            )
        else:
            raise AssertionError(
                f"Invalid batch was accepted: {batch['batch_number']}"
            )

    print("All invalid batch records were rejected.")


# --------------------------------------------------
# TEST 10: LEGACY AGGREGATE STOCK WITHOUT BATCHES
# --------------------------------------------------

def test_legacy_aggregate_stock_without_batches():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 100,
            "consumption_required": 60,
            "safety_stock": 0,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={},
        transport_costs={},
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=[]
    )

    print("Full optimizer result:", result)

    assert result["status"] == "OPTIMAL"

    assert result["shortage"] == []

    # No batch records exist, so no batch-level consumption
    # should be fabricated.
    assert result["batch_consumption"] == []

    # Aggregate stock is sufficient to satisfy consumption.
    assert result["unallocated_consumption"] == []

    print("Aggregate stock:", 100)
    print("Required consumption:", 60)
    print("Shortage:", result["shortage"])
    print("Unallocated:", result["unallocated_consumption"])



# --------------------------------------------------
# TEST 11: AGGREGATE STOCK WITH INSUFFICIENT COVERAGE
# --------------------------------------------------

def test_aggregate_stock_insufficient_coverage():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 30,
            "consumption_required": 50,
            "safety_stock": 0,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={},
        transport_costs={},
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"

    shortage_quantity = sum(
        item["shortage_quantity"]
        for item in result["shortage"]
    )

    unallocated_quantity = sum(
        item["unallocated_quantity"]
        for item in result["unallocated_consumption"]
    )

    assert result["batch_consumption"] == []
    assert shortage_quantity == 20
    assert unallocated_quantity == 20

    print("Aggregate stock: 30")
    print("Required consumption: 50")
    print("Shortage:", shortage_quantity)
    print("Unallocated consumption:", unallocated_quantity)



# --------------------------------------------------
# TEST 12: AGGREGATE STOCK REDISTRIBUTION
# --------------------------------------------------

def test_aggregate_stock_redistribution():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 100,
            "required_stock": 0,
            "transferable_stock": 60,
            "lead_time_days": 0
        },
        {
            "hospital_id": 2,
            "resource_id": 3,
            "usable_stock": 0,
            "required_stock": 50,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={},
        transport_costs={(1, 2): 5},
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"

    transfers = result["redistribution"]

    assert len(transfers) == 1
    assert transfers[0]["source_hospital_id"] == 1
    assert transfers[0]["target_hospital_id"] == 2
    assert transfers[0]["quantity"] == 50

    # Aggregate-only transfers must not invent batch allocations.
    assert transfers[0]["batch_allocations"] == []
    assert result["batch_transfers"] == []

    print("Redistribution:", transfers)
    print("Batch transfers:", result["batch_transfers"])


# --------------------------------------------------
# TEST 13: MISSING TRANSPORT ROUTE
# --------------------------------------------------

def test_missing_transport_route():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 100,
            "required_stock": 0,
            "transferable_stock": 100,
            "lead_time_days": 0
        },
        {
            "hospital_id": 2,
            "resource_id": 3,
            "usable_stock": 0,
            "required_stock": 50,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={},
        transport_costs={},  # No route configured
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"
    assert result["redistribution"] == []
    assert result["batch_transfers"] == []

    print("Redistribution:", result["redistribution"])
    print("Missing route correctly prevented transfer.")


# --------------------------------------------------
# TEST 14: INVALID TRANSPORT COST
# --------------------------------------------------

def test_invalid_transport_cost():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 100,
            "required_stock": 0,
            "transferable_stock": 100,
            "lead_time_days": 0
        },
        {
            "hospital_id": 2,
            "resource_id": 3,
            "usable_stock": 0,
            "required_stock": 50,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    try:
        optimize_resource_allocation(
            inventory_data=inventory_data,
            demand_data={},
            procurement_costs={},
            transport_costs={(1, 2): -5},
            expiry_data={},
            planning_horizon_days=7,
            equipment_data=[]
        )

    except ValueError:
        print("Negative transport cost correctly rejected.")

    else:
        raise AssertionError(
            "Negative transport cost was accepted!"
        )



# --------------------------------------------------
# TEST 15: INVALID PROCUREMENT COST
# --------------------------------------------------

def test_invalid_procurement_cost():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 0,
            "required_stock": 50,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    try:
        optimize_resource_allocation(
            inventory_data=inventory_data,
            demand_data={},
            procurement_costs={3: -10},
            transport_costs={},
            expiry_data={},
            planning_horizon_days=7,
            equipment_data=[]
        )

    except ValueError:
        print("Negative procurement cost correctly rejected.")

    else:
        raise AssertionError(
            "Negative procurement cost was accepted!"
        )


# --------------------------------------------------
# TEST 16: PROCUREMENT LEAD-TIME RESTRICTION
# --------------------------------------------------

def test_procurement_lead_time_restriction():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 0,
            "required_stock": 50,
            "transferable_stock": 0,
            "lead_time_days": 10
        }
    ]

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={3: 100},
        transport_costs={},
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"
    assert result["procurement"] == []

    shortage_quantity = sum(
        item["shortage_quantity"]
        for item in result["shortage"]
    )

    assert shortage_quantity == 50

    print("Supplier lead time: 10 days")
    print("Planning horizon: 7 days")
    print("Procurement:", result["procurement"])
    print("Shortage:", result["shortage"])


# --------------------------------------------------
# TEST 17: PROCUREMENT ALLOWED WITHIN LEAD TIME
# --------------------------------------------------

def test_procurement_within_lead_time():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 0,
            "required_stock": 50,
            "transferable_stock": 0,
            "lead_time_days": 5
        }
    ]

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={3: 10},
        transport_costs={},
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"

    purchased = sum(
        item["quantity"] for item in result["procurement"]
    )

    assert purchased == 50
    assert result["shortage"] == []

    print("Procurement:", result["procurement"])


# --------------------------------------------------
# TEST 18: NO FREE PROCUREMENT WITHOUT PRICE
# --------------------------------------------------

def test_no_free_procurement():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 0,
            "required_stock": 40,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={},
        transport_costs={},
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"
    assert result["procurement"] == []

    shortage_quantity = sum(
        item["shortage_quantity"]
        for item in result["shortage"]
    )

    assert shortage_quantity == 40

    print("Procurement:", result["procurement"])
    print("Shortage:", result["shortage"])


# --------------------------------------------------
# TEST 19: PROCUREMENT QUANTITY VALIDATION
# --------------------------------------------------

def test_procurement_quantity_validation():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 10,
            "required_stock": 50,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={3: 10},
        transport_costs={},
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"

    for item in result["procurement"]:
        assert isinstance(item["quantity"], int)
        assert item["quantity"] > 0

    print("Procurement:", result["procurement"])



# --------------------------------------------------
# TEST 20: ZERO-COST TRANSPORT ROUTE
# --------------------------------------------------

def test_zero_cost_transport_route():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 100,
            "required_stock": 0,
            "transferable_stock": 100,
            "lead_time_days": 0
        },
        {
            "hospital_id": 2,
            "resource_id": 3,
            "usable_stock": 0,
            "required_stock": 50,
            "transferable_stock": 0,
            "lead_time_days": 0
        }
    ]

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={},
        transport_costs={(1, 2): 0},
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL"

    transferred = sum(
        item["quantity"] for item in result["redistribution"]
    )

    assert transferred == 50

    print("Redistribution:", result["redistribution"])


def test_aggregate_transfer_source_consumption():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 100,
            "consumption_required": 30,
            "safety_stock": 0,
            "lead_time_days": 7
        },
        {
            "hospital_id": 2,
            "resource_id": 3,
            "usable_stock": 0,
            "consumption_required": 50,
            "safety_stock": 0,
            "lead_time_days": 7
        }
    ]

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={},
        transport_costs={(1, 2): 1},
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL", result

    transferred = sum(
        item["quantity"]
        for item in result["redistribution"]
    )

    assert transferred == 50, result["redistribution"]
    assert result["unallocated_consumption"] == [], result

    print("Aggregate stock transferred:", transferred)
    print("Unallocated consumption:", result["unallocated_consumption"])



def test_aggregate_incoming_consumption():

    inventory_data = [
        {
            "hospital_id": 1,
            "resource_id": 3,
            "usable_stock": 100,
            "consumption_required": 0,
            "safety_stock": 0,
            "lead_time_days": 7
        },
        {
            "hospital_id": 2,
            "resource_id": 3,
            "usable_stock": 0,
            "consumption_required": 50,
            "safety_stock": 0,
            "lead_time_days": 7
        }
    ]

    result = optimize_resource_allocation(
        inventory_data=inventory_data,
        demand_data={},
        procurement_costs={},
        transport_costs={(1, 2): 1},
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=[]
    )

    assert result["status"] == "OPTIMAL", result

    transferred = sum(
        item["quantity"]
        for item in result["redistribution"]
    )

    assert transferred == 50, result["redistribution"]
    assert result["unallocated_consumption"] == [], result

    print("Incoming aggregate stock:", transferred)
    print("Unallocated consumption:", result["unallocated_consumption"])





# --------------------------------------------------
# RUN ALL TESTS
# --------------------------------------------------

if __name__ == "__main__":
    tests = [
    ("Expiry / Excess Stock", test_expiry_optimizer),
    ("Procurement and Redistribution", test_procurement_optimizer),
    ("FEFO Incoming Transfer", test_fefo_incoming_transfer),
    ("FEFO Multiple Batches", test_fefo_multiple_batches),
    ("Reserved Stock Protection", test_reserved_stock_protection),
    ("Expired-Batch Exclusion", test_expired_batch_exclusion),
    ("Insufficient Stock", test_insufficient_stock),
    ("Zero Stock and Zero Demand", test_zero_stock_and_zero_demand),
    ("Invalid Batch Data Validation", test_invalid_batch_data),
    ("Legacy Aggregate Stock Without Batches",
 test_legacy_aggregate_stock_without_batches),
 ("Aggregate Stock Insufficient Coverage",
 test_aggregate_stock_insufficient_coverage),
 ("Aggregate Stock Redistribution",
 test_aggregate_stock_redistribution),
 ("Missing Transport Route", test_missing_transport_route),
 ("Invalid Transport Cost", test_invalid_transport_cost),
 ("Invalid Procurement Cost", test_invalid_procurement_cost),
 ("Procurement Lead-Time Restriction",
 test_procurement_lead_time_restriction),
 ("Procurement Within Lead Time", test_procurement_within_lead_time),
("No Free Procurement", test_no_free_procurement),
("Procurement Quantity Validation", test_procurement_quantity_validation),
("Zero-Cost Transport Route", test_zero_cost_transport_route),
("Aggregate Transfer Source Consumption",
 test_aggregate_transfer_source_consumption),

("Aggregate Incoming Consumption",
 test_aggregate_incoming_consumption)

]

    passed = 0

    for name, test_function in tests:
        try:
            run_test(name, test_function)
            passed += 1
        except Exception as error:
            print(f"\nFAILED: {name}")
            print(f"Reason: {error}")

    print("\n" + "=" * 55)
    print(f"FINAL RESULT: {passed}/{len(tests)} tests passed")
    print("=" * 55)


def test_criticality_aware_maintenance_decisions():
    equipment_data = [
        {
            "equipment_id": 101,
            "hospital_id": 1,
            "criticality": "HIGH",
            "maintenance_cost": 2500,
            "avoidable_downtime_hours": 1,
        },
        {
            "equipment_id": 102,
            "hospital_id": 1,
            "criticality": "MEDIUM",
            "maintenance_cost": 1800,
            "avoidable_downtime_hours": 1,
        },
        {
            "equipment_id": 103,
            "hospital_id": 1,
            "criticality": "LOW",
            "maintenance_cost": 1200,
            "avoidable_downtime_hours": 1,
        },
    ]

    result = optimize_resource_allocation(
        inventory_data=[],
        demand_data={},
        procurement_costs={},
        transport_costs={},
        expiry_data={},
        planning_horizon_days=7,
        equipment_data=equipment_data,
        downtime_penalty_per_hour=1000,
    )

    assert result["status"] == "OPTIMAL"

    maintenance = result["maintenance"]

    scheduled_ids = {
        item["equipment_id"] for item in maintenance
    }

    assert scheduled_ids == {101, 102}

    high_item = next(
        item for item in maintenance
        if item["equipment_id"] == 101
    )

    medium_item = next(
        item for item in maintenance
        if item["equipment_id"] == 102
    )

    assert high_item["criticality"] == "HIGH"
    assert high_item["weighted_downtime_penalty"] == 3000

    assert medium_item["criticality"] == "MEDIUM"
    assert medium_item["weighted_downtime_penalty"] == 2000