from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Any
from database import get_db
from models import User, Connection, Project
import schemas
from utils.auth import get_current_user, get_current_project
from utils.crypto import encrypt_value, decrypt_value
from utils.db_connector import SQLConnector, MongoConnector

router = APIRouter(prefix="/api/connections", tags=["connections"])

def get_connector(conn: Connection):
    conn_str = decrypt_value(conn.connection_string_encrypted)
    if conn.db_type == "mongodb":
        # Extract db_name from connection string or details if needed. Assuming generic connection string
        return MongoConnector(conn_str, "test_db") 
    else:
        return SQLConnector(conn_str)

@router.post("/", response_model=schemas.ConnectionResponse)
async def create_connection(conn_data: schemas.ConnectionCreate, db: AsyncSession = Depends(get_db), current_project: Project = Depends(get_current_project)):
    encrypted_str = encrypt_value(conn_data.connection_string)
    new_conn = Connection(
        project_id=current_project.id,
        name=conn_data.name,
        db_type=conn_data.db_type,
        connection_string_encrypted=encrypted_str
    )
    db.add(new_conn)
    await db.commit()
    await db.refresh(new_conn)
    return new_conn

@router.get("/", response_model=List[schemas.ConnectionResponse])
async def list_connections(db: AsyncSession = Depends(get_db), current_project: Project = Depends(get_current_project)):
    result = await db.execute(select(Connection).where(Connection.project_id == current_project.id))
    return result.scalars().all()

@router.get("/{id}/schema")
async def get_connection_schema(id: str, db: AsyncSession = Depends(get_db), current_project: Project = Depends(get_current_project)):
    result = await db.execute(select(Connection).where(Connection.id == id, Connection.project_id == current_project.id))
    conn = result.scalars().first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    connector = get_connector(conn)
    try:
        schema = await connector.get_schema()
        return {"schema": schema}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{id}/query")
async def execute_query(id: str, query_payload: Dict[str, Any], db: AsyncSession = Depends(get_db), current_project: Project = Depends(get_current_project)):
    result = await db.execute(select(Connection).where(Connection.id == id, Connection.project_id == current_project.id))
    conn = result.scalars().first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    connector = get_connector(conn)
    try:
        if conn.db_type == "mongodb":
            data = await connector.execute_query(query_payload.get("collection"), query_payload.get("filter", {}))
        else:
            data = await connector.execute_query(query_payload.get("query", ""))
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{id}/test")
async def test_connection_endpoint(id: str, db: AsyncSession = Depends(get_db), current_project: Project = Depends(get_current_project)):
    result = await db.execute(select(Connection).where(Connection.id == id, Connection.project_id == current_project.id))
    conn = result.scalars().first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    connector = get_connector(conn)
    try:
        success = await connector.test_connection()
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")
