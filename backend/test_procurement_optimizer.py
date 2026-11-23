from services.entity_service import optimize_resource_allocation


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

demand_data = {
    (1, 3): 0,
    (2, 3): 0
}

procurement_costs = {
    3: 100
}

transport_costs = {
    (2, 1): 5
}

expiry_data = {}

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