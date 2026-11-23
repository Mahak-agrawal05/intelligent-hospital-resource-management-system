
from services.entity_service import optimize_resource_allocation

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
            "days_until_expiry": 47
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
            "days_until_expiry": 320
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

print("\nOPTIMIZATION RESULT:")
print("Status:", result["status"])
print("Transfers:", result["batch_transfers"])
print("Consumption:", result["batch_consumption"])

receiver_consumption = [
    item for item in result["batch_consumption"]
    if item["hospital_id"] == 2
]

assert result["status"] == "OPTIMAL"
assert sum(x["quantity"] for x in result["batch_transfers"]) == 60

assert receiver_consumption[0]["batch_number"] == "INCOMING-EARLY"
assert receiver_consumption[0]["quantity"] == 60

assert receiver_consumption[1]["batch_number"] == "LOCAL-LATE"
assert receiver_consumption[1]["quantity"] == 20

print("\nTEST 10.1.1 PASSED!")
