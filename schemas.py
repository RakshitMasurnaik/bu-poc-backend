from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any, Dict
from datetime import datetime

# --- Auth & User Schemas ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    organization_name: str

class InviteRequest(BaseModel):
    email: EmailStr

class ActivateRequest(BaseModel):
    token: str
    password: str
    full_name: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    global_role: str
    organization_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class OrganizationResponse(BaseModel):
    id: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True

class OrganizationWithProjectsResponse(OrganizationResponse):
    projects: List["ProjectResponse"] = []

    class Config:
        from_attributes = True

# --- Project Schemas ---
class ProjectCreate(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: str
    organization_id: Optional[str] = None
    name: str
    created_at: datetime

    class Config:
        from_attributes = True

class ProjectMemberCreate(BaseModel):
    user_id: str
    role: str = "viewer" # 'viewer', 'editor'

class ProjectMemberUpdate(BaseModel):
    role: str

class ProjectMemberResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    role: str
    created_at: datetime
    user: UserResponse

    class Config:
        from_attributes = True

# --- Connection Schemas ---
class ConnectionCreate(BaseModel):
    name: str
    db_type: str # postgres, mysql, sqlite, mongodb
    connection_string: Optional[str] = None
    # For explicit details instead of connection string
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None

class ConnectionResponse(BaseModel):
    id: str
    project_id: str
    name: str
    db_type: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# --- Business Schema Schemas ---
class LogicalField(BaseModel):
    name: str
    type: str # Email, Phone, Currency, Date, String, Integer
    required: bool = False
    validation_regex: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None

class BusinessSchemaCreate(BaseModel):
    name: str
    description: Optional[str] = None
    fields: List[LogicalField]

class BusinessSchemaResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    fields: List[LogicalField]
    connection_id: Optional[str] = None
    physical_target_name: Optional[str] = None
    field_mappings: Optional[List[Dict[str, str]]] = None

    class Config:
        from_attributes = True

class FieldMapping(BaseModel):
    logical_field: str
    physical_column: str

class SchemaMapRequest(BaseModel):
    connection_id: str
    physical_target_name: str
    field_mappings: List[FieldMapping]

class ValidationRunResponse(BaseModel):
    id: str
    schema_id: str
    compliance_score: str
    total_records: str
    compliant_records: str
    created_at: datetime

    class Config:
        from_attributes = True
