from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from database import get_db
from models import User, ProjectMember, Project, Organization
import schemas
from utils.auth import get_current_user, require_org_admin, require_platform_admin
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/api/organizations", tags=["organizations"])

@router.get("/", response_model=List[schemas.OrganizationWithProjectsResponse])
async def get_all_organizations(current_user: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organization).options(selectinload(Organization.projects)))
    return result.scalars().all()

class MemberResponse(BaseModel):
    id: str
    email: str
    full_name: str
    global_role: str

    class Config:
        from_attributes = True

@router.get("/members", response_model=List[MemberResponse])
async def get_org_members(org_id: str = None, current_user: User = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    target_org_id = current_user.organization_id
    if current_user.global_role == "platform_admin" and org_id:
        target_org_id = org_id
    result = await db.execute(select(User).where(User.organization_id == target_org_id))
    return result.scalars().all()

class UpdateOrgRole(BaseModel):
    role: str

@router.put("/members/{user_id}/role")
async def update_org_member_role(user_id: str, data: UpdateOrgRole, current_user: User = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    if data.role not in ["user", "org_admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
        
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalars().first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if current_user.global_role != "platform_admin" and target_user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Cannot modify user outside your organization")
        
    target_user.global_role = data.role
    await db.commit()
    return {"message": "Role updated successfully"}

@router.delete("/members/{user_id}")
async def remove_org_member(user_id: str, current_user: User = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalars().first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if current_user.global_role != "platform_admin" and target_user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Cannot modify user outside your organization")
        
    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
        
    target_user.organization_id = None
    # Also delete project memberships for this user in this org
    # (Leaving it simple for now, as DB might cascade or we can just let project memberships persist until cleaned up, or explicitly delete them)
    await db.execute(
        ProjectMember.__table__.delete().where(
            ProjectMember.user_id == user_id
        )
    )
    await db.commit()
    return {"message": "User removed from organization"}

@router.get("/{org_id}/users", response_model=List[schemas.UserResponse])
async def get_specific_org_users(org_id: str, current_user: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.organization_id == org_id))
    return result.scalars().all()
