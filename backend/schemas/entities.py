from datetime import date

from pydantic import BaseModel, Field


# =========================================================
# 1. HOSPITAL
# =========================================================

class HospitalCreate(BaseModel):

    hospital_name: str

    location: str

    hospital_type: str


# =========================================================
# 2. USER
# =========================================================

class UserCreate(BaseModel):

    name: str

    email: str

    password_hash: str

    role: str

    hospital_id: int


# =========================================================
# 3. RESOURCE
# =========================================================

class ResourceCreate(BaseModel):

    resource_name: str

    category: str

    unit: str

    supplier_id: int | None = None

    reorder_level: int = Field(ge=0)

    safety_stock: int = Field(ge=0)

    lead_time_days: int = Field(ge=0)


# =========================================================
# 4. INVENTORY
# =========================================================

class InventoryCreate(BaseModel):

    hospital_id: int

    resource_id: int

    current_quantity: int = Field(ge=0)

    reserved_quantity: int = Field(ge=0)


# =========================================================
# 5. RESOURCE BATCH
# =========================================================

class ResourceBatchCreate(BaseModel):

    inventory_id: int

    batch_number: str

    quantity: int = Field(ge=0)

    manufacturing_date: date | None = None

    expiry_date: date

    received_date: date | None = None


# =========================================================
# 6. CONSUMPTION HISTORY
# =========================================================

class ConsumptionHistoryCreate(BaseModel):

    hospital_id: int

    resource_id: int

    consumption_date: date

    quantity_consumed: int = Field(ge=0)


# =========================================================
# 7. SUPPLIER
# =========================================================

class SupplierCreate(BaseModel):

    supplier_name: str

    contact_info: str | None = None

    average_lead_time: int = Field(ge=0)

    reliability_score: float | None = Field(
        default=None,
        ge=0,
        le=100
    )


# =========================================================
# 8. EQUIPMENT
# =========================================================

class EquipmentCreate(BaseModel):

    hospital_id: int

    equipment_name: str

    equipment_type: str

    manufacturer: str | None = None

    model_number: str | None = None

    installation_date: date | None = None

    status: str


# =========================================================
# 9. MAINTENANCE RECORD
# =========================================================

class MaintenanceRecordCreate(BaseModel):

    equipment_id: int

    maintenance_date: date

    maintenance_type: str

    downtime_hours: float | None = Field(
        default=None,
        ge=0
    )

    maintenance_cost: float | None = Field(
        default=None,
        ge=0
    )

    failure_reason: str | None = None

    notes: str | None = None



class LoginRequest(BaseModel):
    email: str
    password: str