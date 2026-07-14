from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from database import get_db
from models import User, BusinessSchema, Connection, ValidationRun, Project
import schemas
from utils.auth import get_current_user, get_current_project
from routers.connections import get_connector
from utils.validator import validate_field

router = APIRouter(prefix="/api/schemas", tags=["schemas"])

@router.post("/", response_model=schemas.BusinessSchemaResponse)
async def create_schema(schema_data: schemas.BusinessSchemaCreate, db: AsyncSession = Depends(get_db), current_project: Project = Depends(get_current_project)):
    new_schema = BusinessSchema(
        project_id=current_project.id,
        name=schema_data.name,
        description=schema_data.description,
        fields=[field.dict() for field in schema_data.fields]
    )
    db.add(new_schema)
    await db.commit()
    await db.refresh(new_schema)
    return new_schema

@router.get("/", response_model=List[schemas.BusinessSchemaResponse])
async def list_schemas(db: AsyncSession = Depends(get_db), current_project: Project = Depends(get_current_project)):
    result = await db.execute(select(BusinessSchema).where(BusinessSchema.project_id == current_project.id))
    schemas_db = result.scalars().all()
    return schemas_db

@router.post("/{id}/map")
async def map_schema(id: str, mapping_data: schemas.SchemaMapRequest, db: AsyncSession = Depends(get_db), current_project: Project = Depends(get_current_project)):
    result = await db.execute(select(BusinessSchema).where(BusinessSchema.id == id, BusinessSchema.project_id == current_project.id))
    b_schema = result.scalars().first()
    if not b_schema:
        raise HTTPException(status_code=404, detail="Schema not found")
        
    b_schema.connection_id = mapping_data.connection_id
    b_schema.physical_target_name = mapping_data.physical_target_name
    b_schema.field_mappings = [m.dict() for m in mapping_data.field_mappings]
    
    await db.commit()
    return {"status": "success", "message": "Schema mapped successfully"}

@router.post("/{id}/validate")
async def validate_schema(id: str, db: AsyncSession = Depends(get_db), current_project: Project = Depends(get_current_project)):
    # 1. Fetch schema and connection
    result = await db.execute(select(BusinessSchema).where(BusinessSchema.id == id))
    b_schema = result.scalars().first()
    if not b_schema or not b_schema.connection_id:
        raise HTTPException(status_code=400, detail="Schema not ready for validation (missing mapping)")
        
    conn_result = await db.execute(select(Connection).where(Connection.id == b_schema.connection_id))
    conn = conn_result.scalars().first()
    
    connector = get_connector(conn)
    
    # 2. Fetch data based on physical target
    target = b_schema.physical_target_name
    try:
        if conn.db_type == "mongodb":
            data = await connector.execute_query(target, {}, limit=100)
        else:
            data = await connector.execute_query(f"SELECT * FROM {target} LIMIT 100")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch data: {str(e)}")

    # 3. Validate
    logical_fields = {f['name']: f for f in b_schema.fields}
    mappings = {m['logical_field']: m['physical_column'] for m in (b_schema.field_mappings or [])}
    
    total = len(data)
    compliant = 0
    errors = []
    
    for row_idx, row in enumerate(data):
        row_valid = True
        for l_name, p_name in mappings.items():
            val = row.get(p_name)
            field_def = logical_fields.get(l_name)
            if not field_def: continue
            
            if val is None and field_def.get("required"):
                row_valid = False
                errors.append({"row": row_idx, "field": l_name, "error": "Missing required field"})
                continue
                
            if val is not None:
                is_valid, err_msg = validate_field(val, field_def["type"], field_def)
                if not is_valid:
                    row_valid = False
                    errors.append({"row": row_idx, "field": l_name, "error": err_msg, "value": val})
                    
        if row_valid:
            compliant += 1
            
    score = (compliant / total * 100) if total > 0 else 100

    # Persist Validation Run
    new_run = ValidationRun(
        schema_id=id,
        compliance_score=str(score),
        total_records=str(total),
        compliant_records=str(compliant)
    )
    db.add(new_run)
    await db.commit()
    
    return {
        "total_records_tested": total,
        "compliant_records": compliant,
        "compliance_score": score,
        "errors": errors
    }

@router.get("/validation-history", response_model=List[schemas.ValidationRunResponse])
async def get_validation_history(db: AsyncSession = Depends(get_db), current_project: Project = Depends(get_current_project)):
    # Get all validation runs for schemas belonging to this user's project
    result = await db.execute(
        select(ValidationRun)
        .join(BusinessSchema, BusinessSchema.id == ValidationRun.schema_id)
        .where(BusinessSchema.project_id == current_project.id)
        .order_by(ValidationRun.created_at.asc())
    )
    runs = result.scalars().all()
    return runs
