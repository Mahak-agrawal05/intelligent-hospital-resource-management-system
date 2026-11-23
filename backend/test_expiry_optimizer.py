from services.entity_service import optimize_resource_allocation


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

demand_data = {
    (99, 99): 0
}

procurement_costs = {
    99: 10
}

transport_costs = {}

expiry_data = {
    (99, 99): {
        "expiry_date": "2026-10-06",
        "days_until_expiry": 5,
        "batch_quantity": 100
    }
}

result = optimize_resource_allocation(
    inventory_data=inventory_data,
    demand_data=demand_data,
    procurement_costs=procurement_costs,
    transport_costs=transport_costs,
    expiry_data=expiry_data,
    planning_horizon_days=7,
    equipment_data=[]
)

print(result)