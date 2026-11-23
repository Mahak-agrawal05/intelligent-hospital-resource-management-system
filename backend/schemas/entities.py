from datetime import date

from pydantic import BaseModel, Field

from pydantic import field_validator


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
    password: str


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
    criticality: str = "MEDIUM"

    @field_validator("criticality")
    @classmethod
    def validate_criticality(cls, value):
        value = value.upper().strip()

        if value not in ("HIGH", "MEDIUM", "LOW"):
            raise ValueError(
                "Criticality must be HIGH, MEDIUM, or LOW"
            )

        return value


class ResourceBatchCreate(BaseModel):

    inventory_id: int

    batch_number: str

    quantity: int = Field(ge=0)

    reserved_quantity: int = Field(default=0, ge=0)

    manufacturing_date: date | None = None

    expiry_date: date

    received_date: date | None = None


# =========================================================
# 4. INVENTORY
# =========================================================

class InventoryCreate(BaseModel):

    hospital_id: int

    resource_id: int

    current_quantity: int = Field(ge=0)

    reserved_quantity: int = Field(ge=0)


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

    criticality: str = "MEDIUM"

    @field_validator("criticality")
    @classmethod
    def validate_criticality(cls, value):
        value = value.upper().strip()

        if value not in ("URGENT", "HIGH", "MEDIUM", "LOW"):
            raise ValueError(
                "Criticality must be URGENT, HIGH, MEDIUM, or LOW"
            )

        return value


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


from datetime import date
from pydantic import BaseModel, Field


class ProcurementReceiptCreate(BaseModel):
    batch_number: str = Field(..., min_length=1, max_length=100)
    expiry_date: date
    manufacturing_date: date | None = None
    received_date: date | None = None

from datetime import date
from pydantic import BaseModel, Field


class ProcurementReceiptCreate(BaseModel):
    batch_number: str = Field(..., min_length=1, max_length=100)
    expiry_date: date
    manufacturing_date: date | None = None
    received_date: date | None = None