import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from database import get_db
from models import User, Project, ProjectMember

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-development-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 day

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

async def require_platform_admin(current_user: User = Depends(get_current_user)):
    if current_user.global_role != "platform_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin access required")
    return current_user

async def require_org_admin(current_user: User = Depends(get_current_user)):
    if current_user.global_role not in ["platform_admin", "org_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin access required")
    return current_user

async def get_current_project(
    x_project_id: Optional[str] = Header(None), 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not x_project_id:
        raise HTTPException(status_code=400, detail="X-Project-Id header missing")
        
    result = await db.execute(select(Project).where(Project.id == x_project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check access
    if current_user.global_role in ["platform_admin", "org_admin"]:
        # Org Admins can access all projects in their org
        if current_user.global_role == "org_admin" and project.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Access denied")
        return project

    # Standard users must be members of the project
    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == current_user.id
        )
    )
    membership = member_result.scalars().first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Access denied to this project")
        
    # We could attach membership to the project object temporarily if needed, e.g., project.current_user_role = membership.role
    return project
